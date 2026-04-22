#pragma once

#include <string>
#include <functional>
#include <memory>
#include <unordered_map>
#include <mutex>

namespace avframework {

class WebSocketServer {
public:
    using MessageHandler = std::function<void(int, const std::string&)>;
    using ConnectionHandler = std::function<void(int, bool)>;

    WebSocketServer(int port = 8081);
    ~WebSocketServer();

    bool start();
    void stop();

    void setMessageHandler(MessageHandler handler) { message_handler_ = std::move(handler); }
    void setConnectionHandler(ConnectionHandler handler) { connection_handler_ = std::move(handler); }

    void send(int client_id, const std::string& message);
    void broadcast(const std::string& message);
    void close(int client_id);

private:
    struct ClientConnection {
        int fd;
        std::string buffer;
        bool is_handshaked;
    };

    void serverLoop();
    void handleClient(int client_id);
    bool performHandshake(int client_fd, const std::string& handshake_data);
    std::string decodeFrame(const std::string& frame);
    std::string encodeFrame(const std::string& message);
    void removeClient(int client_id);
    static std::string base64_encode(const unsigned char* data, size_t len);

    int port_;
    int server_fd_;
    std::atomic<bool> running_;

    std::unordered_map<int, ClientConnection> clients_;
    std::mutex clients_mutex_;
    int next_client_id_;

    MessageHandler message_handler_;
    ConnectionHandler connection_handler_;
};

}
