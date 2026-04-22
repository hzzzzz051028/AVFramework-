#include "http_server.h"
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <thread>
#include <sstream>
#include <regex>

namespace avframework {

HTTPServer::HTTPServer(int port)
    : port_(port)
    , server_fd_(-1)
    , running_(false)
    , cors_enabled_(true)
{
}

HTTPServer::~HTTPServer() {
    stop();
}

bool HTTPServer::start() {
    server_fd_ = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd_ < 0) {
        return false;
    }

    int opt = 1;
    setsockopt(server_fd_, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in address;
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(port_);

    if (bind(server_fd_, (struct sockaddr*)&address, sizeof(address)) < 0) {
        close(server_fd_);
        return false;
    }

    if (listen(server_fd_, 10) < 0) {
        close(server_fd_);
        return false;
    }

    running_ = true;
    std::thread(&HTTPServer::serverLoop, this).detach();

    return true;
}

void HTTPServer::stop() {
    running_ = false;
    if (server_fd_ >= 0) {
        close(server_fd_);
        server_fd_ = -1;
    }
}

void HTTPServer::serverLoop() {
    while (running_) {
        struct sockaddr_in client_addr;
        socklen_t addr_len = sizeof(client_addr);

        int client_fd = accept(server_fd_, (struct sockaddr*)&client_addr, &addr_len);
        if (client_fd < 0) {
            continue;
        }

        std::thread(&HTTPServer::handleConnection, this, client_fd).detach();
    }
}

void HTTPServer::handleConnection(int client_fd) {
    char buffer[4096] = {0};
    ssize_t bytes_read = recv(client_fd, buffer, sizeof(buffer) - 1, 0);

    if (bytes_read <= 0) {
        close(client_fd);
        return;
    }

    std::string request(buffer);
    std::istringstream iss(request);
    std::string method, path, version;

    iss >> method >> path >> version;

    std::string body;
    if (method == "POST" || method == "PUT") {
        size_t content_length_pos = request.find("Content-Length:");
        if (content_length_pos != std::string::npos) {
            size_t colon_pos = request.find("\r\n", content_length_pos);
            std::string length_str = request.substr(content_length_pos + 16, colon_pos - content_length_pos - 16);
            int content_length = std::stoi(length_str);

            size_t header_end = request.find("\r\n\r\n");
            if (header_end != std::string::npos && content_length > 0) {
                body = request.substr(header_end + 4, content_length);
            }
        }
    }

    std::string response_body = "{\"error\":\"Not Found\"}";
    std::string content_type = "application/json";
    int status_code = 404;

    auto& handlers = method == "GET" ? get_handlers_ :
                     method == "POST" ? post_handlers_ :
                     method == "PUT" ? put_handlers_ : delete_handlers_;

    for (const auto& [route, handler] : handlers) {
        std::regex pattern(route);
        if (std::regex_match(path, pattern)) {
            response_body = handler(path, body);
            status_code = 200;
            break;
        }
    }

    std::string response = generateHTTPResponse(status_code, content_type, response_body);
    send(client_fd, response.c_str(), response.length(), 0);
    close(client_fd);
}

std::string HTTPServer::generateHTTPResponse(int status_code, const std::string& content_type, const std::string& body) {
    std::string status_text = status_code == 200 ? "OK" :
                              status_code == 201 ? "Created" :
                              status_code == 404 ? "Not Found" : "Error";

    std::ostringstream response;
    response << "HTTP/1.1 " << status_code << " " << status_text << "\r\n";
    response << "Content-Type: " << content_type << "\r\n";
    response << "Content-Length: " << body.length() << "\r\n";

    if (cors_enabled_) {
        response << "Access-Control-Allow-Origin: *\r\n";
        response << "Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS\r\n";
        response << "Access-Control-Allow-Headers: Content-Type\r\n";
    }

    response << "\r\n";
    response << body;

    return response.str();
}

void HTTPServer::setRouteHandler(const std::string& method, const std::string& path, RequestHandler handler) {
    if (method == "GET") {
        get_handlers_[path] = std::move(handler);
    } else if (method == "POST") {
        post_handlers_[path] = std::move(handler);
    } else if (method == "PUT") {
        put_handlers_[path] = std::move(handler);
    } else if (method == "DELETE") {
        delete_handlers_[path] = std::move(handler);
    }
}

}
