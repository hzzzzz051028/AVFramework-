#pragma once

#include "av_common.h"
#include <string>
#include <functional>
#include <memory>

namespace avframework {

class HTTPServer {
public:
    using RequestHandler = std::function<std::string(const std::string&, const std::string&)>;

    HTTPServer(int port = 8080);
    ~HTTPServer();

    bool start();
    void stop();

    void setRouteHandler(const std::string& method, const std::string& path, RequestHandler handler);

    void setCORS(bool enabled = true) { cors_enabled_ = enabled; }

private:
    void serverLoop();
    void handleConnection(int client_fd);
    std::string generateHTTPResponse(int status_code, const std::string& content_type, const std::string& body);
    std::string parseRequestPath(const std::string& request);

    int port_;
    int server_fd_;
    std::atomic<bool> running_;

    std::unordered_map<std::string, RequestHandler> get_handlers_;
    std::unordered_map<std::string, RequestHandler> post_handlers_;
    std::unordered_map<std::string, RequestHandler> put_handlers_;
    std::unordered_map<std::string, RequestHandler> delete_handlers_;

    bool cors_enabled_;
};

}
