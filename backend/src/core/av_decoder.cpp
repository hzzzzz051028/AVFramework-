#include "av_decoder.h"
#include <iostream>

namespace avframework {

AVDecoder::AVDecoder()
    : format_ctx_(nullptr)
    , video_codec_ctx_(nullptr)
    , audio_codec_ctx_(nullptr)
    , video_stream_index_(-1)
    , audio_stream_index_(-1)
    , video_width_(0)
    , video_height_(0)
    , duration_(0.0)
    , opened_(false)
{
}

AVDecoder::~AVDecoder() {
    close();
}

AVResult AVDecoder::open(const std::string& url) {
    format_ctx_ = avformat_alloc_context();

    int ret = avformat_open_input(&format_ctx_, url.c_str(), nullptr, nullptr);
    if (ret != 0) {
        return AVResult::Error;
    }

    ret = avformat_find_stream_info(format_ctx_, nullptr);
    if (ret < 0) {
        avformat_close_input(&format_ctx_);
        return AVResult::Error;
    }

    duration_ = format_ctx_->duration / (double)AV_TIME_BASE;

    AVResult result = openVideoStream();
    if (result != AVResult::Success) {
        close();
        return result;
    }

    openAudioStream();

    opened_ = true;
    return AVResult::Success;
}

void AVDecoder::close() {
    if (video_codec_ctx_) {
        avcodec_free_context(&video_codec_ctx_);
        video_codec_ctx_ = nullptr;
    }

    if (audio_codec_ctx_) {
        avcodec_free_context(&audio_codec_ctx_);
        audio_codec_ctx_ = nullptr;
    }

    if (format_ctx_) {
        avformat_close_input(&format_ctx_);
        format_ctx_ = nullptr;
    }

    opened_ = false;
}

AVResult AVDecoder::openVideoStream() {
    video_stream_index_ = av_find_best_stream(format_ctx_,
        AVMEDIA_TYPE_VIDEO, -1, -1, nullptr, 0);

    if (video_stream_index_ < 0) {
        return AVResult::Error;
    }

    AVStream* stream = format_ctx_->streams[video_stream_index_];
    const AVCodec* codec = avcodec_find_decoder(stream->codecpar->codec_id);

    if (!codec) {
        return AVResult::Error;
    }

    video_codec_ctx_ = avcodec_alloc_context3(codec);
    avcodec_parameters_to_context(video_codec_ctx_, stream->codecpar);

    int ret = avcodec_open2(video_codec_ctx_, codec, nullptr);
    if (ret < 0) {
        avcodec_free_context(&video_codec_ctx_);
        video_codec_ctx_ = nullptr;
        return AVResult::Error;
    }

    video_width_ = video_codec_ctx_->width;
    video_height_ = video_codec_ctx_->height;

    return AVResult::Success;
}

AVResult AVDecoder::openAudioStream() {
    audio_stream_index_ = av_find_best_stream(format_ctx_,
        AVMEDIA_TYPE_AUDIO, -1, -1, nullptr, 0);

    if (audio_stream_index_ < 0) {
        return AVResult::Error;
    }

    AVStream* stream = format_ctx_->streams[audio_stream_index_];
    const AVCodec* codec = avcodec_find_decoder(stream->codecpar->codec_id);

    if (!codec) {
        return AVResult::Error;
    }

    audio_codec_ctx_ = avcodec_alloc_context3(codec);
    avcodec_parameters_to_context(audio_codec_ctx_, stream->codecpar);

    int ret = avcodec_open2(audio_codec_ctx_, codec, nullptr);
    if (ret < 0) {
        avcodec_free_context(&audio_codec_ctx_);
        audio_codec_ctx_ = nullptr;
        return AVResult::Error;
    }

    return AVResult::Success;
}

AVResult AVDecoder::readFrame(std::shared_ptr<AVFrameData>& frame) {
    if (!opened_) {
        return AVResult::Error;
    }

    AVPacket* packet = av_packet_alloc();
    AVFrame* avframe = av_frame_alloc();

    int ret = av_read_frame(format_ctx_, packet);
    if (ret < 0) {
        av_packet_free(&packet);
        av_frame_free(&avframe);
        return ret == AVERROR_EOF ? AVResult::Eof : AVResult::Error;
    }

    AVCodecContext* codec_ctx = nullptr;
    int stream_index = -1;

    if (packet->stream_index == video_stream_index_) {
        codec_ctx = video_codec_ctx_;
        stream_index = video_stream_index_;
    } else if (packet->stream_index == audio_stream_index_) {
        codec_ctx = audio_codec_ctx_;
        stream_index = audio_stream_index_;
    }

    if (codec_ctx) {
        ret = avcodec_send_packet(codec_ctx, packet);
        if (ret >= 0) {
            ret = avcodec_receive_frame(codec_ctx, avframe);
            if (ret >= 0) {
                frame = std::make_shared<AVFrameData>();
                frame->timestamp = avframe->pts;
                frame->is_video = (stream_index == video_stream_index_);

                if (frame->is_video) {
                    int size = av_image_get_buffer_size(
                        static_cast<AVPixelFormat>(avframe->format),
                        avframe->width, avframe->height, 1);
                    frame->data = static_cast<uint8_t*>(av_malloc(size));
                    av_image_copy_to_buffer(frame->data, size,
                        avframe->data, avframe->linesize,
                        static_cast<AVPixelFormat>(avframe->format),
                        avframe->width, avframe->height, 1);
                    frame->size = size;
                }

                if (data_callback_) {
                    data_callback_(frame);
                }
            }
        }
    }

    av_packet_free(&packet);
    av_frame_free(&avframe);

    return AVResult::Success;
}

AVResult AVDecoder::seek(int64_t timestamp) {
    if (!opened_) {
        return AVResult::Error;
    }

    int64_t seek_target = timestamp * AV_TIME_BASE;
    av_seek_frame(format_ctx_, -1, seek_target, AVSEEK_FLAG_BACKWARD);

    return AVResult::Success;
}

}
