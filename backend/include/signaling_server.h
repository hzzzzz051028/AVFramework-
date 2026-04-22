#pragma once

#include "websocket_server.h"
#include <string>
#include <functional>
#include <unordered_map>
#include <mutex>
#include <nlohmann/json.hpp>

namespace avframework {

struct WebRTCSession {
    std::string session_id;
    std::string host_client_id;
    std::string guest_client_id;
    std::string host_sdp;
    std::string guest_sdp;
    std::vector<std::string> host_ice_candidates;
    std::vector<std::string> guest_ice_candidates;
    bool is_ready;
};

class SignalingServer {
public:
    SignalingServer(int port = 8081);
    ~SignalingServer();

    bool start();
    void stop();

    using SessionCallback = std::function<void(const std::string&, const std::string&)>;
    using OfferCallback = std::function<void(const std::string&, const std::string&, const std::string&)>;

    void setSessionCreatedCallback(SessionCallback callback) { session_created_callback_ = std::move(callback); }
    void setOfferCallback(OfferCallback callback) { offer_callback_ = std::move(callback); }

    std::string createSession(const std::string& client_id);
    bool joinSession(const std::string& session_id, const std::string& client_id);
    bool leaveSession(const std::string& session_id, const std::string& client_id);

    void exchangeSDP(const std::string& session_id, const std::string& client_id, const std::string& sdp);
    void exchangeICECandidate(const std::string& session_id, const std::string& client_id, const std::string& candidate);

private:
    void handleSignalingMessage(int client_id, const std::string& message);
    void handleConnection(int client_id, bool connected);

    std::unique_ptr<WebSocketServer> ws_server_;

    std::unordered_map<std::string, WebRTCSession> sessions_;
    std::mutex sessions_mutex_;

    std::unordered_map<int, std::string> client_to_session_;
    std::mutex client_mutex_;

    SessionCallback session_created_callback_;
    OfferCallback offer_callback_;
};

}
