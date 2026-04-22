#pragma once

#include <string>
#include <memory>
#include <functional>
#include <queue>
#include <mutex>

extern "C" {
#include <libavcodec/avcodec.h>
#include <libavformat/avformat.h>
#include <libavutil/avutil.h>
#include <libavutil/imgutils.h>
#include <libswscale/swscale.h>
#include <libswresample/swresample.h>
}

namespace avframework {

enum class AVResult {
    Success = 0,
    Error = -1,
    Eof = -2,
    TryAgain = -3
};

struct AVConfig {
    int video_width = 1920;
    int video_height = 1080;
    int video_framerate = 30;
    int video_bitrate = 4000000;

    int audio_samplerate = 48000;
    int audio_channels = 2;
    int audio_bitrate = 128000;

    std::string output_format = "hls";
    std::string output_path = "./output";
};

struct AVFrameData {
    uint8_t* data = nullptr;
    size_t size = 0;
    int64_t timestamp = 0;
    bool is_video = true;

    ~AVFrameData() {
        if (data) {
            av_free(data);
        }
    }
};

using AVDataCallback = std::function<void(std::shared_ptr<AVFrameData>)>;

}
