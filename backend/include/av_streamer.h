#pragma once

#include "av_common.h"
#include <string>
#include <memory>
#include <unordered_map>
#include <mutex>
#include <functional>

namespace avframework {

struct StreamInfo {
    std::string stream_id;
    std::string stream_url;
    std::string protocol;
    int width;
    int height;
    int framerate;
    bool is_active;

    std::string hls_path;
    std::string dash_path;
};

class AVStreamer {
public:
    AVStreamer();
    ~AVStreamer();

    struct StreamConfig {
        std::string protocol = "rtmp";
        int rtmp_port = 1935;
        int http_port = 8080;
        std::string hls_output_dir = "./hls";
        int hls_time = 2;
        int hls_list_size = 5;
    };

    bool init(const StreamConfig& config);
    void shutdown();

    std::string createStream(const std::string& stream_id, const AVConfig& config);
    bool removeStream(const std::string& stream_id);

    bool startPublish(const std::string& stream_id, const std::string& source_url);
    void stopPublish(const std::string& stream_id);

    std::string getStreamUrl(const std::string& stream_id, const std::string& protocol = "hls");
    StreamInfo getStreamInfo(const std::string& stream_id);

    std::vector<StreamInfo> listStreams();

    void setStreamStateCallback(std::function<void(const std::string&, bool)> callback) {
        state_callback_ = std::move(callback);
    }

private:
    bool startHLSStream(const std::string& stream_id, const std::string& source_url);
    bool startRTMPStream(const std::string& stream_id, const std::string& source_url);
    bool startDASHStream(const std::string& stream_id, const std::string& source_url);

    void generateHLSPlaylist(const std::string& stream_id);
    void generateDASHManifest(const std::string& stream_id);

    StreamConfig config_;
    std::unordered_map<std::string, StreamInfo> streams_;
    std::mutex streams_mutex_;

    std::function<void(const std::string&, bool)> state_callback_;

    struct StreamContext {
        std::unique_ptr<class AVEncoder> encoder;
        std::unique_ptr<class AVDecoder> decoder;
        std::thread publish_thread;
        std::atomic<bool> publishing;
    };

    std::unordered_map<std::string, StreamContext> stream_contexts_;
};

}
