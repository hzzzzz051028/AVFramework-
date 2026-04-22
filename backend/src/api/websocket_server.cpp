#include "websocket_server.h"

#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <wincrypt.h>
#pragma comment(lib, "ws2_32.lib")
#else
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <fcntl.h>
#include <openssl/sha.h>
#include <errno.h>
#endif

#include <thread>
#include <sstream>
#include <cstring>
#include <random>

namespace avframework {

#ifdef _WIN32
#define sys_close(fd) closesocket(fd)
#else
#define sys_close(fd) ::close(fd)
#endif

WebSocketServer::WebSocketServer(int port)
    : port_(port)
    , server_fd_(-1)
    , running_(false)
    , next_client_id_(1)
{
}

WebSocketServer::~WebSocketServer() {
    stop();
}

bool WebSocketServer::start() {
#ifdef _WIN32
    WSADATA wsa_data;
    int result = WSAStartup(MAKEWORD(2, 2), &wsa_data);
    if (result != 0) {
        return false;
    }
#endif

    server_fd_ = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (server_fd_ < 0) {
#ifdef _WIN32
        WSACleanup();
#endif
        return false;
    }

    int opt = 1;
    setsockopt(server_fd_, SOL_SOCKET, SO_REUSEADDR, (const char*)&opt, sizeof(opt));

    struct sockaddr_in address;
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(port_);

    if (bind(server_fd_, (struct sockaddr*)&address, sizeof(address)) < 0) {
        sys_close(server_fd_);
#ifdef _WIN32
        WSACleanup();
#endif
        return false;
    }

    if (listen(server_fd_, 10) < 0) {
        sys_close(server_fd_);
#ifdef _WIN32
        WSACleanup();
#endif
        return false;
    }

    running_ = true;
    std::thread(&WebSocketServer::serverLoop, this).detach();

    return true;
}

void WebSocketServer::stop() {
    running_ = false;

    if (server_fd_ >= 0) {
        sys_close(server_fd_);
        server_fd_ = -1;
    }

#ifdef _WIN32
    WSACleanup();
#endif
}

void WebSocketServer::serverLoop() {
    while (running_) {
        struct sockaddr_in client_addr;
        socklen_t addr_len = sizeof(client_addr);

        int client_fd = accept(server_fd_, (struct sockaddr*)&client_addr, &addr_len);
        if (client_fd < 0) {
            continue;
        }

        int client_id = next_client_id_++;

        {
            std::lock_guard<std::mutex> lock(clients_mutex_);
            clients_[client_id] = {client_fd, "", false};
        }

        std::thread(&WebSocketServer::handleClient, this, client_id).detach();

        if (connection_handler_) {
            connection_handler_(client_id, true);
        }
    }
}

void WebSocketServer::handleClient(int client_id) {
    char buffer[4096] = {0};
    ClientConnection* client = nullptr;

    {
        std::lock_guard<std::mutex> lock(clients_mutex_);
        auto it = clients_.find(client_id);
        if (it == clients_.end()) return;
        client = &it->second;
    }

    while (running_) {
        int bytes_read = recv(client->fd, buffer, sizeof(buffer), 0);
        if (bytes_read <= 0) {
            break;
        }

        client->buffer.append(buffer, bytes_read);

        if (!client->is_handshaked) {
            size_t header_end = client->buffer.find("\r\n\r\n");
            if (header_end != std::string::npos) {
                std::string handshake_data = client->buffer.substr(0, header_end);
                client->buffer = client->buffer.substr(header_end + 4);

                if (performHandshake(client->fd, handshake_data)) {
                    client->is_handshaked = true;
                } else {
                    break;
                }
            }
        } else {
            while (client->buffer.size() >= 2) {
                auto [message, frame_size] = decodeFrame(client->buffer);
                if (frame_size == 0) break;
                client->buffer = client->buffer.substr(frame_size);
                if (!message.empty() && message_handler_) {
                    message_handler_(client_id, message);
                }
            }
        }
    }

    removeClient(client_id);
}

bool WebSocketServer::performHandshake(int client_fd, const std::string& handshake_data) {
    size_t key_pos = handshake_data.find("Sec-WebSocket-Key:");
    if (key_pos == std::string::npos) {
        return false;
    }

    size_t key_start = key_pos + 19;
    size_t key_end = handshake_data.find("\r\n", key_start);
    std::string client_key = handshake_data.substr(key_start, key_end - key_start);

    std::string magic_key = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11";
    std::string combined = client_key + magic_key;

    unsigned char hash[SHA_DIGEST_LENGTH] = {0};

#ifdef _WIN32
    HCRYPTPROV hProv = 0;
    HCRYPTHASH hHash = 0;
    DWORD hashLen = SHA_DIGEST_LENGTH;

    CryptAcquireContext(&hProv, NULL, NULL, PROV_RSA_FULL, CRYPT_VERIFYCONTEXT);
    CryptCreateHash(hProv, CALG_SHA1, 0, 0, &hHash);
    CryptHashData(hHash, reinterpret_cast<const BYTE*>(combined.c_str()), combined.length(), 0);
    CryptGetHashParam(hHash, HP_HASHVAL, hash, &hashLen, 0);
    CryptDestroyHash(hHash);
    CryptReleaseContext(hProv, 0);
#else
    SHA1(reinterpret_cast<const unsigned char*>(combined.c_str()), combined.length(), hash);
#endif

    std::string accept_key = base64_encode(hash, SHA_DIGEST_LENGTH);

    std::ostringstream response;
    response << "HTTP/1.1 101 Switching Protocols\r\n";
    response << "Upgrade: websocket\r\n";
    response << "Connection: Upgrade\r\n";
    response << "Sec-WebSocket-Accept: " << accept_key << "\r\n\r\n";

    ::send(client_fd, response.str().c_str(), response.str().length(), 0);

    return true;
}

std::pair<std::string, size_t> WebSocketServer::decodeFrame(const std::string& frame) {
    if (frame.size() < 2) return {"", 0};

    uint8_t first_byte = static_cast<uint8_t>(frame[0]);
    uint8_t second_byte = static_cast<uint8_t>(frame[1]);

    bool fin = (first_byte & 0x80) != 0;
    uint8_t opcode = first_byte & 0x0F;
    bool masked = (second_byte & 0x80) != 0;
    uint64_t payload_length = second_byte & 0x7F;

    size_t header_size = 2;

    if (payload_length == 126) {
        if (frame.size() < 4) return {"", 0};
        payload_length = (static_cast<uint8_t>(frame[2]) << 8) | static_cast<uint8_t>(frame[3]);
        header_size = 4;
    } else if (payload_length == 127) {
        if (frame.size() < 10) return {"", 0};
        payload_length = 0;
        for (int i = 0; i < 8; i++) {
            payload_length = (payload_length << 8) | static_cast<uint8_t>(frame[2 + i]);
        }
        header_size = 10;
    }

    size_t mask_size = masked ? 4 : 0;
    if (frame.size() < header_size + mask_size + payload_length) return {"", 0};

    size_t payload_offset = header_size + mask_size;
    std::string payload = frame.substr(payload_offset, payload_length);

    if (masked && payload_length > 0) {
        const char* mask = frame.data() + header_size;
        for (size_t i = 0; i < payload_length; i++) {
            payload[i] ^= mask[i % 4];
        }
    }

    size_t frame_size = header_size + mask_size + payload_length;
    return {payload, frame_size};
}

std::string WebSocketServer::encodeFrame(const std::string& message) {
    std::string frame;
    frame.push_back(0x81);

    size_t message_size = message.size();
    if (message_size < 126) {
        frame.push_back(static_cast<char>(message_size));
    } else if (message_size < 65536) {
        frame.push_back(126);
        frame.push_back(static_cast<char>((message_size >> 8) & 0xFF));
        frame.push_back(static_cast<char>(message_size & 0xFF));
    } else {
        frame.push_back(127);
        for (int i = 7; i >= 0; i--) {
            frame.push_back(static_cast<char>((message_size >> (i * 8)) & 0xFF));
        }
    }

    frame += message;
    return frame;
}

void WebSocketServer::send(int client_id, const std::string& message) {
    std::lock_guard<std::mutex> lock(clients_mutex_);
    auto it = clients_.find(client_id);
    if (it != clients_.end()) {
        std::string frame = encodeFrame(message);
        ::send(it->second.fd, frame.c_str(), frame.length(), 0);
    }
}

void WebSocketServer::broadcast(const std::string& message) {
    std::lock_guard<std::mutex> lock(clients_mutex_);
    std::string frame = encodeFrame(message);

    for (auto& [id, client] : clients_) {
        if (client.is_handshaked) {
            ::send(client.fd, frame.c_str(), frame.length(), 0);
        }
    }
}

void WebSocketServer::close(int client_id) {
    removeClient(client_id);
}

void WebSocketServer::removeClient(int client_id) {
    std::lock_guard<std::mutex> lock(clients_mutex_);
    auto it = clients_.find(client_id);
    if (it != clients_.end()) {
        sys_close(it->second.fd);
        clients_.erase(it);

        if (connection_handler_) {
            connection_handler_(client_id, false);
        }
    }
}

std::string WebSocketServer::base64_encode(const unsigned char* data, size_t len) {
    const char* chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    std::string result;
    result.reserve(((len + 2) / 3) * 4);

    for (size_t i = 0; i < len; i += 3) {
        unsigned int value = (data[i] << 16);
        if (i + 1 < len) value |= (data[i + 1] << 8);
        if (i + 2 < len) value |= data[i + 2];

        result.push_back(chars[(value >> 18) & 0x3F]);
        result.push_back(chars[(value >> 12) & 0x3F]);
        result.push_back((i + 1 < len) ? chars[(value >> 6) & 0x3F] : '=');
        result.push_back((i + 2 < len) ? chars[value & 0x3F] : '=');
    }

    return result;
}

}
