#include "av_encoder.h"
#include <iostream>

namespace avframework {

AVEncoder::AVEncoder()
    : format_ctx_(nullptr)
    , video_codec_ctx_(nullptr)
    , audio_codec_ctx_(nullptr)
    , video_stream_index_(-1)
    , audio_stream_index_(-1)
    , opened_(false)
    , header_written_(false)
{
}

AVEncoder::~AVEncoder() {
    close();
}

AVResult AVEncoder::open(const AVConfig& config, const std::string& output_url) {
    config_ = config;
    output_url_ = output_url;

    int ret = avformat_alloc_output_context2(&format_ctx_, nullptr,
        nullptr, output_url.c_str());
    if (ret < 0 || !format_ctx_) {
        return AVResult::Error;
    }

    AVResult result = initVideoStream();
    if (result != AVResult::Success) {
        close();
        return result;
    }

    result = initAudioStream();
    if (result != AVResult::Success) {
        close();
        return result;
    }

    if (!(format_ctx_->oformat->flags & AVFMT_NOFILE)) {
        ret = avio_open(&format_ctx_->pb, output_url.c_str(), AVIO_FLAG_WRITE);
        if (ret < 0) {
            close();
            return AVResult::Error;
        }
    }

    result = writeHeader();
    if (result != AVResult::Success) {
        close();
        return result;
    }

    opened_ = true;
    return AVResult::Success;
}

void AVEncoder::close() {
    if (opened_) {
        writeTrailer();
    }

    if (video_codec_ctx_) {
        avcodec_free_context(&video_codec_ctx_);
        video_codec_ctx_ = nullptr;
    }

    if (audio_codec_ctx_) {
        avcodec_free_context(&audio_codec_ctx_);
        audio_codec_ctx_ = nullptr;
    }

    if (format_ctx_) {
        if (!(format_ctx_->oformat->flags & AVFMT_NOFILE)) {
            avio_closep(&format_ctx_->pb);
        }
        avformat_free_context(format_ctx_);
        format_ctx_ = nullptr;
    }

    opened_ = false;
    header_written_ = false;
}

AVResult AVEncoder::initVideoStream() {
    const AVCodec* codec = avcodec_find_encoder(AV_CODEC_ID_H264);
    if (!codec) {
        return AVResult::Error;
    }

    video_codec_ctx_ = avcodec_alloc_context3(codec);
    video_codec_ctx_->width = config_.video_width;
    video_codec_ctx_->height = config_.video_height;
    video_codec_ctx_->time_base = {1, config_.video_framerate};
    video_codec_ctx_->framerate = {config_.video_framerate, 1};
    video_codec_ctx_->gop_size = 12;
    video_codec_ctx_->max_b_frames = 1;
    video_codec_ctx_->pix_fmt = AV_PIX_FMT_YUV420P;
    video_codec_ctx_->bit_rate = config_.video_bitrate;

    if (format_ctx_->oformat->flags & AVFMT_GLOBALHEADER) {
        video_codec_ctx_->flags |= AV_CODEC_FLAG_GLOBAL_HEADER;
    }

    int ret = avcodec_open2(video_codec_ctx_, codec, nullptr);
    if (ret < 0) {
        return AVResult::Error;
    }

    AVStream* stream = avformat_new_stream(format_ctx_, nullptr);
    if (!stream) {
        return AVResult::Error;
    }

    stream->time_base = video_codec_ctx_->time_base;
    ret = avcodec_parameters_from_context(stream->codecpar, video_codec_ctx_);
    if (ret < 0) {
        return AVResult::Error;
    }

    video_stream_index_ = stream->index;

    return AVResult::Success;
}

AVResult AVEncoder::initAudioStream() {
    const AVCodec* codec = avcodec_find_encoder(AV_CODEC_ID_AAC);
    if (!codec) {
        return AVResult::Error;
    }

    audio_codec_ctx_ = avcodec_alloc_context3(codec);
    audio_codec_ctx_->sample_rate = config_.audio_samplerate;
    audio_codec_ctx_->sample_fmt = codec->sample_fmts ? codec->sample_fmts[0] : AV_SAMPLE_FMT_FLTP;
    audio_codec_ctx_->bit_rate = config_.audio_bitrate;
    audio_codec_ctx_->time_base = {1, config_.audio_samplerate};

    // 设置通道布局 (FFmpeg 7.0+ API)
    av_channel_layout_default(&audio_codec_ctx_->ch_layout, config_.audio_channels);

    if (format_ctx_->oformat->flags & AVFMT_GLOBALHEADER) {
        audio_codec_ctx_->flags |= AV_CODEC_FLAG_GLOBAL_HEADER;
    }

    int ret = avcodec_open2(audio_codec_ctx_, codec, nullptr);
    if (ret < 0) {
        return AVResult::Error;
    }

    AVStream* stream = avformat_new_stream(format_ctx_, nullptr);
    if (!stream) {
        return AVResult::Error;
    }

    stream->time_base = audio_codec_ctx_->time_base;
    ret = avcodec_parameters_from_context(stream->codecpar, audio_codec_ctx_);
    if (ret < 0) {
        return AVResult::Error;
    }

    audio_stream_index_ = stream->index;

    return AVResult::Success;
}

AVResult AVEncoder::writeHeader() {
    int ret = avformat_write_header(format_ctx_, nullptr);
    if (ret < 0) {
        return AVResult::Error;
    }
    header_written_ = true;
    return AVResult::Success;
}

AVResult AVEncoder::writeTrailer() {
    if (!header_written_) {
        return AVResult::Error;
    }

    int ret = av_write_trailer(format_ctx_);
    if (ret < 0) {
        return AVResult::Error;
    }

    return AVResult::Success;
}

AVResult AVEncoder::writeFrame(std::shared_ptr<AVFrameData> frame) {
    if (!opened_ || !frame) {
        return AVResult::Error;
    }

    AVFrame* avframe = av_frame_alloc();
    AVPacket* packet = av_packet_alloc();

    AVCodecContext* codec_ctx = frame->is_video ? video_codec_ctx_ : audio_codec_ctx_;
    int stream_index = frame->is_video ? video_stream_index_ : audio_stream_index_;

    avframe->pts = frame->timestamp;

    int ret = avcodec_send_frame(codec_ctx, avframe);
    if (ret >= 0) {
        ret = avcodec_receive_packet(codec_ctx, packet);
        if (ret == 0) {
            av_packet_rescale_ts(packet, codec_ctx->time_base,
                format_ctx_->streams[stream_index]->time_base);
            packet->stream_index = stream_index;

            ret = av_interleaved_write_frame(format_ctx_, packet);
            if (ret < 0) {
                av_packet_free(&packet);
                av_frame_free(&avframe);
                return AVResult::Error;
            }
        }
    }

    av_packet_free(&packet);
    av_frame_free(&avframe);

    return AVResult::Success;
}

AVResult AVEncoder::flush() {
    AVPacket* packet = av_packet_alloc();

    for (auto codec_ctx : {video_codec_ctx_, audio_codec_ctx_}) {
        if (!codec_ctx) continue;

        avcodec_send_frame(codec_ctx, nullptr);
        while (avcodec_receive_packet(codec_ctx, packet) == 0) {
            av_interleaved_write_frame(format_ctx_, packet);
            av_packet_unref(packet);
        }
    }

    av_packet_free(&packet);
    return AVResult::Success;
}

}
