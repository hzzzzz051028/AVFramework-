#pragma once

#include "av_common.h"
#include <atomic>

namespace avframework {

class AVDecoder {
public:
    AVDecoder();
    ~AVDecoder();

    AVResult open(const std::string& url);
    void close();

    AVResult readFrame(std::shared_ptr<AVFrameData>& frame);
    AVResult seek(int64_t timestamp);

    bool isOpened() const { return opened_; }
    int getVideoWidth() const { return video_width_; }
    int getVideoHeight() const { return video_height_; }
    double getDuration() const { return duration_; }

    void setDataCallback(AVDataCallback callback) {
        data_callback_ = std::move(callback);
    }

private:
    AVResult openVideoStream();
    AVResult openAudioStream();

    AVFormatContext* format_ctx_;
    AVCodecContext* video_codec_ctx_;
    AVCodecContext* audio_codec_ctx_;

    int video_stream_index_;
    int audio_stream_index_;

    int video_width_;
    int video_height_;
    double duration_;

    std::atomic<bool> opened_;
    AVDataCallback data_callback_;
};

}
