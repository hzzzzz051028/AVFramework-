#pragma once

#include "av_common.h"

namespace avframework {

class AVEncoder {
public:
    AVEncoder();
    ~AVEncoder();

    AVResult open(const AVConfig& config, const std::string& output_url);
    void close();

    AVResult writeFrame(std::shared_ptr<AVFrameData> frame);
    AVResult flush();

    bool isOpened() const { return opened_; }

private:
    AVResult initVideoStream();
    AVResult initAudioStream();
    AVResult writeHeader();
    AVResult writeTrailer();

    AVFormatContext* format_ctx_;
    AVCodecContext* video_codec_ctx_;
    AVCodecContext* audio_codec_ctx_;

    int video_stream_index_;
    int audio_stream_index_;

    AVConfig config_;
    std::string output_url_;

    std::atomic<bool> opened_;
    bool header_written_;
};

}
