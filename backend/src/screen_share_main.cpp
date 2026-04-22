#include <iostream>
#include <memory>
#include <csignal>

#include "../include/webrtc/signaling_server.h"
#include "../include/utils/logger.h"

using namespace avframework;

static bool g_running = false;

void signalHandler(int signal) {
    std::cout << "\nShutting down..." << std::endl;
    g_running = false;
}

int main(int argc, char* argv[]) {
    std::signal(SIGINT, signalHandler);
    std::signal(SIGTERM, signalHandler);

    std::cout << "\n========================================\n";
    std::cout << "   Screen Share Server\n";
    std::cout << "========================================\n\n";

    int websocket_port = 8081;

    // Parse command line arguments
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--port" && i + 1 < argc) {
            websocket_port = std::atoi(argv[++i]);
        } else if (arg == "--help") {
            std::cout << "Usage: " << argv[0] << " [--port PORT]\n";
            std::cout << "  --port PORT    WebSocket port (default: 8081)\n";
            std::cout << "  --help         Show help\n";
            return 0;
        }
    }

    std::cout << "Configuration:\n";
    std::cout << "  WebSocket Port: " << websocket_port << "\n\n";

    // Create signaling server
    auto signaling_server = std::make_unique<SignalingServer>(websocket_port);

    // Set callback
    signaling_server->setSessionCreatedCallback([](const std::string& session_id, const std::string& client_id) {
        std::cout << "[Callback] Session created: " << session_id << " by client " << client_id << std::endl;
    });

    // Start server
    if (!signaling_server->start()) {
        std::cerr << "Failed to start signaling server" << std::endl;
        return 1;
    }

    std::cout << "\n========================================\n";
    std::cout << "   Server Started\n";
    std::cout << "========================================\n\n";
    std::cout << "To use:\n";
    std::cout << "  1. Open screenshare.html in browser\n";
    std::cout << "  2. Select 'Share Screen' mode\n";
    std::cout << "  3. Click 'Start Sharing'\n\n";
    std::cout << "WebSocket: ws://localhost:" << websocket_port << "\n\n";
    std::cout << "Press Ctrl+C to stop\n";
    std::cout << "========================================\n\n";

    g_running = true;
    while (g_running) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    std::cout << "\nStopping server..." << std::endl;
    signaling_server->stop();

    std::cout << "Server stopped" << std::endl;
    return 0;
}
