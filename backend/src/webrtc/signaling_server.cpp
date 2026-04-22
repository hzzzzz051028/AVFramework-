#include "signaling_server.h"
#include <random>
#include <sstream>

namespace avframework {

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
    return ws_server_->start();
}

void SignalingServer::stop() {
    ws_server_->stop();
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

bool SignalingServer::joinSession(const std::string& session_id, const std::string& client_id) {
    std::lock_guard<std::mutex> lock(sessions_mutex_);

    auto it = sessions_.find(session_id);
    if (it == sessions_.end() || it->second.guest_client_id.empty() == false) {
        return false;
    }

    it->second.guest_client_id = client_id;
    it->second.is_ready = true;

    {
        std::lock_guard<std::mutex> client_lock(client_mutex_);
        client_to_session_[std::stoi(client_id)] = session_id;
    }

    return true;
}

bool SignalingServer::leaveSession(const std::string& session_id, const std::string& client_id) {
    std::lock_guard<std::mutex> lock(sessions_mutex_);

    auto it = sessions_.find(session_id);
    if (it == sessions_.end()) {
        return false;
    }

    {
        std::lock_guard<std::mutex> client_lock(client_mutex_);
        auto client_it = client_to_session_.find(std::stoi(client_id));
        if (client_it != client_to_session_.end() && client_it->second == session_id) {
            client_to_session_.erase(client_it);
        }
    }

    if (it->second.host_client_id == client_id) {
        sessions_.erase(it);
    } else if (it->second.guest_client_id == client_id) {
        it->second.guest_client_id.clear();
        it->second.is_ready = false;
    }

    return true;
}

void SignalingServer::exchangeSDP(const std::string& session_id, const std::string& client_id, const std::string& sdp) {
    std::lock_guard<std::mutex> lock(sessions_mutex_);

    auto it = sessions_.find(session_id);
    if (it == sessions_.end()) {
        return;
    }

    nlohmann::json msg;
    msg["type"] = "sdp";
    msg["sdp"] = sdp;
    msg["sender"] = client_id;

    std::string target_client_id;

    if (it->second.host_client_id == client_id) {
        it->second.host_sdp = sdp;
        target_client_id = it->second.guest_client_id;
    } else if (it->second.guest_client_id == client_id) {
        it->second.guest_sdp = sdp;
        target_client_id = it->second.host_client_id;
    }

    if (!target_client_id.empty()) {
        ws_server_->send(std::stoi(target_client_id), msg.dump());
    }
}

void SignalingServer::exchangeICECandidate(const std::string& session_id, const std::string& client_id, const std::string& candidate) {
    std::lock_guard<std::mutex> lock(sessions_mutex_);

    auto it = sessions_.find(session_id);
    if (it == sessions_.end()) {
        return;
    }

    nlohmann::json msg;
    msg["type"] = "ice";
    msg["candidate"] = candidate;
    msg["sender"] = client_id;

    std::string target_client_id;

    if (it->second.host_client_id == client_id) {
        it->second.host_ice_candidates.push_back(candidate);
        target_client_id = it->second.guest_client_id;
    } else if (it->second.guest_client_id == client_id) {
        it->second.guest_ice_candidates.push_back(candidate);
        target_client_id = it->second.host_client_id;
    }

    if (!target_client_id.empty()) {
        ws_server_->send(std::stoi(target_client_id), msg.dump());
    }
}

void SignalingServer::handleSignalingMessage(int client_id, const std::string& message) {
    try {
        nlohmann::json msg = nlohmann::json::parse(message);

        std::string type = msg["type"];
        std::string client_id_str = std::to_string(client_id);

        if (type == "create_session") {
            std::string session_id = createSession(client_id_str);

            nlohmann::json response;
            response["type"] = "session_created";
            response["session_id"] = session_id;
            ws_server_->send(client_id, response.dump());

        } else if (type == "join_session") {
            std::string session_id = msg["session_id"];
            bool success = joinSession(session_id, client_id_str);

            nlohmann::json response;
            response["type"] = "session_joined";
            response["success"] = success;
            ws_server_->send(client_id, response.dump());

        } else if (type == "offer") {
            std::string session_id = msg["session_id"];
            std::string sdp = msg["sdp"];

            {
                std::lock_guard<std::mutex> client_lock(client_mutex_);
                auto it = client_to_session_.find(client_id);
                if (it != client_to_session_.end()) {
                    session_id = it->second;
                }
            }

            exchangeSDP(session_id, client_id_str, sdp);

            if (offer_callback_) {
                offer_callback_(session_id, client_id_str, sdp);
            }

        } else if (type == "answer") {
            std::string session_id = msg["session_id"];
            std::string sdp = msg["sdp"];

            {
                std::lock_guard<std::mutex> client_lock(client_mutex_);
                auto it = client_to_session_.find(client_id);
                if (it != client_to_session_.end()) {
                    session_id = it->second;
                }
            }

            exchangeSDP(session_id, client_id_str, sdp);

        } else if (type == "ice_candidate") {
            std::string session_id = msg["session_id"];
            std::string candidate = msg["candidate"];

            {
                std::lock_guard<std::mutex> client_lock(client_mutex_);
                auto it = client_to_session_.find(client_id);
                if (it != client_to_session_.end()) {
                    session_id = it->second;
                }
            }

            exchangeICECandidate(session_id, client_id_str, candidate);
        }

    } catch (const std::exception& e) {
        // Handle JSON parse errors
    }
}

void SignalingServer::handleConnection(int client_id, bool connected) {
    if (!connected) {
        std::lock_guard<std::mutex> client_lock(client_mutex_);
        auto it = client_to_session_.find(client_id);
        if (it != client_to_session_.end()) {
            leaveSession(it->second, std::to_string(client_id));
        }
    }
}

}
