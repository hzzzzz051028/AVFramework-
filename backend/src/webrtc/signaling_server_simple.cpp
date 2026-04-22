#include <iostream>
#include <map>
#include <mutex>
#include <random>
#include <sstream>

#include "signaling_server.h"

using namespace avframework;

SignalingServer::SignalingServer(int port) {
    ws_server_ = std::make_unique<WebSocketServer>(port);
    ws_server_->setMessageHandler([this](int client_id, const std::string& msg) {
        handleSignalingMessage(client_id, msg);
    });
    ws_server_->setConnectionHandler([this](int client_id, bool connected) {
        handleConnection(client_id, connected);
    });
}

SignalingServer::~SignalingServer() {
    stop();
}

bool SignalingServer::start() {
    std::cout << "Starting WebRTC Signaling Server on port " << ws_server_->getPort() << "..." << std::endl;
    return ws_server_->start();
}

void SignalingServer::stop() {
    ws_server_->stop();
}

void SignalingServer::handleSignalingMessage(int client_id, const std::string& message) {
    try {
        nlohmann::json msg = nlohmann::json::parse(message);
        std::string type = msg["type"];

        std::cout << "[Signaling] Received: " << type << " from client " << client_id << std::endl;

        if (type == "create_session") {
            // 创建新会话（共享者发起）
            std::string session_id = createSession(std::to_string(client_id));

            // 如果有 offer，立即处理
            if (msg.contains("offer")) {
                std::string offer = msg["offer"];

                {
                    std::lock_guard<std::mutex> lock(sessions_mutex_);
                    sessions_[session_id].host_sdp = offer;
                    sessions_[session_id].is_ready = true;
                }

                // 通知会话创建成功
                nlohmann::json response;
                response["type"] = "session_created";
                response["session_id"] = session_id;
                ws_server_->send(client_id, response.dump());

                std::cout << "[Signaling] Session created: " << session_id << std::endl;

                // 广播 offer 给所有等待的观看者
                broadcastOffer(session_id);
            }

        } else if (type == "join_session") {
            // 加入会话（观看者发起）
            std::string session_id = msg["session_id"];

            {
                std::lock_guard<std::mutex> client_lock(client_mutex_);
                client_to_session_[client_id] = session_id;
            }

            std::lock_guard<std::mutex> lock(sessions_mutex_);
            auto it = sessions_.find(session_id);

            if (it != sessions_.end() && !it->second.host_sdp.empty()) {
                // 会话存在且有 offer，立即发送给观看者
                nlohmann::json response;
                response["type"] = "offer";
                response["offer"] = it->second.host_sdp;
                ws_server_->send(client_id, response.dump());

                it->second.guest_client_id = std::to_string(client_id);
                std::cout << "[Signaling] Client " << client_id << " joined session: " << session_id << std::endl;
            } else {
                // 会话不存在或还未就绪
                nlohmann::json response;
                response["type"] = "error";
                response["message"] = "Session not found or not ready";
                ws_server_->send(client_id, response.dump());
            }

        } else if (type == "answer") {
            // 观看者发送 answer
            std::string session_id = msg["session_id"];
            std::string sdp = msg["sdp"];

            std::lock_guard<std::mutex> lock(sessions_mutex_);
            auto it = sessions_.find(session_id);

            if (it != sessions_.end()) {
                it->second.guest_sdp = sdp;

                // 转发 answer 给共享者
                int host_id = std::stoi(it->second.host_client_id);
                if (host_id > 0) {
                    nlohmann::json response;
                    response["type"] = "answer";
                    response["sdp"] = sdp;
                    ws_server_->send(host_id, response.dump());
                    std::cout << "[Signaling] Answer forwarded to host" << std::endl;
                }
            }

        } else if (type == "ice_candidate") {
            // ICE 候选交换
            std::string session_id = msg["session_id"];
            std::string candidate = msg["candidate"];

            std::lock_guard<std::mutex> lock(sessions_mutex_);
            auto it = sessions_.find(session_id);

            if (it != sessions_.end()) {
                std::string target_client_id;

                // 判断是共享者还是观看者发送的
                if (std::to_string(client_id) == it->second.host_client_id) {
                    // 共享者发送 -> 转发给观看者
                    target_client_id = it->second.guest_client_id;
                } else if (std::to_string(client_id) == it->second.guest_client_id) {
                    // 观看者发送 -> 转发给共享者
                    target_client_id = it->second.host_client_id;
                }

                if (!target_client_id.empty()) {
                    nlohmann::json response;
                    response["type"] = "ice";
                    response["candidate"] = candidate;
                    ws_server_->send(std::stoi(target_client_id), response.dump());
                }
            }
        }

    } catch (const std::exception& e) {
        std::cerr << "[Signaling] Error handling message: " << e.what() << std::endl;
    }
}

void SignalingServer::handleConnection(int client_id, bool connected) {
    std::cout << "[Signaling] Client " << client_id << " " << (connected ? "connected" : "disconnected") << std::endl;

    if (!connected) {
        // 清理客户端会话
        std::lock_guard<std::mutex> client_lock(client_mutex_);
        auto it = client_to_session_.find(client_id);

        if (it != client_to_session_.end()) {
            std::string session_id = it->second;

            std::lock_guard<std::mutex> lock(sessions_mutex_);
            auto session_it = sessions_.find(session_id);

            if (session_it != sessions_.end()) {
                // 如果是共享者断开，删除整个会话
                if (session_it->second.host_client_id == std::to_string(client_id)) {
                    sessions_.erase(session_it);
                    std::cout << "[Signaling] Session removed: " << session_id << std::endl;
                } else {
                    // 如果是观看者断开，移除观看者
                    session_it->second.guest_client_id.clear();
                }
            }

            client_to_session_.erase(it);
        }
    }
}

std::string SignalingServer::createSession(const std::string& client_id) {
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(100000, 999999);

    std::string session_id = "sess_" + std::to_string(dis(gen));

    std::lock_guard<std::mutex> lock(sessions_mutex_);

    WebRTCSession session;
    session.session_id = session_id;
    session.host_client_id = client_id;
    session.is_ready = false;

    sessions_[session_id] = session;

    {
        std::lock_guard<std::mutex> client_lock(client_mutex_);
        client_to_session_[std::stoi(client_id)] = session_id;
    }

    if (session_created_callback_) {
        session_created_callback_(session_id, client_id);
    }

    return session_id;
}

void SignalingServer::broadcastOffer(const std::string& session_id) {
    std::lock_guard<std::mutex> lock(sessions_mutex_);
    auto it = sessions_.find(session_id);

    if (it != sessions_.end() && !it->second.host_sdp.empty()) {
        // 发送给等待中的观看者
        // 这里简化处理，实际可以维护等待队列
    }
}
