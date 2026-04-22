#include "av_streamer.h"
#include "av_decoder.h"
#include "av_encoder.h"
#include <fstream>
#include <sstream>
#include <filesystem>
#include <thread>

namespace avframework {

AVStreamer::AVStreamer() {
}

AVStreamer::~AVStreamer() {
    shutdown();
}

bool AVStreamer::init(const StreamConfig& config) {
    config_ = config;

    std::filesystem::create_directories(config_.hls_output_dir);

    return true;
}

void AVStreamer::shutdown() {
    for (auto& [stream_id, context] : stream_contexts_) {
        context.publishing = false;
        if (context.publish_thread.joinable()) {
            context.publish_thread.join();
        }
    }
    stream_contexts_.clear();
    streams_.clear();
}

std::string AVStreamer::createStream(const std::string& stream_id, const AVConfig& config) {
    std::lock_guard<std::mutex> lock(streams_mutex_);

    if (streams_.find(stream_id) != streams_.end()) {
        return streams_[stream_id].stream_url;
    }

    StreamInfo info;
    info.stream_id = stream_id;
    info.width = config.video_width;
    info.height = config.video_height;
    info.framerate = config.video_framerate;
    info.is_active = false;

    std::filesystem::create_directories(config_.hls_output_dir + "/" + stream_id);

    info.hls_path = config_.hls_output_dir + "/" + stream_id;
    info.dash_path = config_.hls_output_dir + "/" + stream_id + "/dash";

    std::filesystem::create_directories(info.dash_path);

    streams_[stream_id] = info;

    return getStreamUrl(stream_id, "hls");
}

bool AVStreamer::removeStream(const std::string& stream_id) {
    std::lock_guard<std::mutex> lock(streams_mutex_);

    auto it = streams_.find(stream_id);
    if (it == streams_.end()) {
        return false;
    }

    stopPublish(stream_id);

    std::filesystem::remove_all(it->second.hls_path);

    streams_.erase(it);
    return true;
}

bool AVStreamer::startPublish(const std::string& stream_id, const std::string& source_url) {
    std::lock_guard<std::mutex> lock(streams_mutex_);

    auto it = streams_.find(stream_id);
    if (it == streams_.end()) {
        return false;
    }

    if (stream_contexts_.find(stream_id) != stream_contexts_.end()) {
        return false;
    }

    it->second.is_active = true;
    it->second.stream_url = source_url;

    bool success = startHLSStream(stream_id, source_url);

    if (success && state_callback_) {
        state_callback_(stream_id, true);
    }

    return success;
}

void AVStreamer::stopPublish(const std::string& stream_id) {
    auto ctx_it = stream_contexts_.find(stream_id);
    if (ctx_it != stream_contexts_.end()) {
        ctx_it->second.publishing = false;
        if (ctx_it->second.publish_thread.joinable()) {
            ctx_it->second.publish_thread.join();
        }
        stream_contexts_.erase(ctx_it);
    }

    auto it = streams_.find(stream_id);
    if (it != streams_.end()) {
        it->second.is_active = false;
        if (state_callback_) {
            state_callback_(stream_id, false);
        }
    }
}

bool AVStreamer::startHLSStream(const std::string& stream_id, const std::string& source_url) {
    auto& info = streams_[stream_id];
    auto& ctx = stream_contexts_[stream_id];

    ctx.encoder = std::make_unique<AVEncoder>();
    ctx.decoder = std::make_unique<AVDecoder>();

    if (ctx.decoder->open(source_url) != AVResult::Success) {
        return false;
    }

    AVConfig config;
    config.video_width = info.width;
    config.video_height = info.height;
    config.video_framerate = info.framerate;

    std::string output_path = info.hls_path + "/stream.m3u8";

    if (ctx.encoder->open(config, output_path) != AVResult::Success) {
        ctx.decoder->close();
        return false;
    }

    ctx.publishing = true;

    ctx.publish_thread = std::thread([this, stream_id]() {
        auto& ctx = stream_contexts_[stream_id];

        while (ctx.publishing) {
            std::shared_ptr<AVFrameData> frame;
            auto result = ctx.decoder->readFrame(frame);

            if (result == AVResult::Eof) {
                break;
            } else if (result != AVResult::Success) {
                break;
            }

            ctx.encoder->writeFrame(frame);
        }

        generateHLSPlaylist(stream_id);
        ctx.publishing = false;
    });

    return true;
}

bool AVStreamer::startRTMPStream(const std::string& stream_id, const std::string& source_url) {
    return false;
}

bool AVStreamer::startDASHStream(const std::string& stream_id, const std::string& source_url) {
    return false;
}

std::string AVStreamer::getStreamUrl(const std::string& stream_id, const std::string& protocol) {
    auto it = streams_.find(stream_id);
    if (it == streams_.end()) {
        return "";
    }

    if (protocol == "hls") {
        return "http://localhost:" + std::to_string(config_.http_port) +
               "/hls/" + stream_id + "/stream.m3u8";
    } else if (protocol == "dash") {
        return "http://localhost:" + std::to_string(config_.http_port) +
               "/dash/" + stream_id + "/manifest.mpd";
    } else if (protocol == "rtmp") {
        return "rtmp://localhost:" + std::to_string(config_.rtmp_port) +
               "/live/" + stream_id;
    }

    return "";
}

StreamInfo AVStreamer::getStreamInfo(const std::string& stream_id) {
    auto it = streams_.find(stream_id);
    if (it != streams_.end()) {
        return it->second;
    }
    return StreamInfo{};
}

std::vector<StreamInfo> AVStreamer::listStreams() {
    std::vector<StreamInfo> result;
    for (const auto& [id, info] : streams_) {
        result.push_back(info);
    }
    return result;
}

void AVStreamer::generateHLSPlaylist(const std::string& stream_id) {
    auto it = streams_.find(stream_id);
    if (it == streams_.end()) return;

    const auto& info = it->second;
    std::string playlist_path = info.hls_path + "/stream.m3u8";

    std::ofstream playlist(playlist_path);
    if (!playlist.is_open()) return;

    playlist << "#EXTM3U\n";
    playlist << "#EXT-X-VERSION:3\n";
    playlist << "#EXT-X-TARGETDURATION:" << config_.hls_time << "\n";
    playlist << "#EXT-X-MEDIA-SEQUENCE:0\n";

    for (int i = 0; i < config_.hls_list_size; i++) {
        playlist << "#EXTINF:" << config_.hls_time << ",\n";
        playlist << "segment_" << std::setfill('0') << std::setw(4) << i << ".ts\n";
    }

    playlist << "#EXT-X-ENDLIST\n";
    playlist.close();
}

void AVStreamer::generateDASHManifest(const std::string& stream_id) {
    auto it = streams_.find(stream_id);
    if (it == streams_.end()) return;

    const auto& info = it->second;
    std::string manifest_path = info.dash_path + "/manifest.mpd";

    std::ofstream manifest(manifest_path);
    if (!manifest.is_open()) return;

    manifest << "<?xml version=\"1.0\"?>\n";
    manifest << "<MPD xmlns=\"urn:mpeg:dash:schema:mpd:2011\" type=\"static\">\n";
    manifest << "  <Period>\n";
    manifest << "    <AdaptationSet mimeType=\"video/mp4\">\n";
    manifest << "      <Representation bandwidth=\"4000000\" width=\""
             << info.width << "\" height=\"" << info.height << "\">\n";
    manifest << "        <SegmentList>\n";
    manifest << "          <SegmentURL media=\"segment_0.m4s\"/>\n";
    manifest << "        </SegmentList>\n";
    manifest << "      </Representation>\n";
    manifest << "    </AdaptationSet>\n";
    manifest << "  </Period>\n";
    manifest << "</MPD>\n";
    manifest.close();
}

}
