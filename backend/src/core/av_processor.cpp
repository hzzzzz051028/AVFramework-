#include "av_processor.h"
#include <thread>
#include <chrono>

namespace avframework {

AVProcessor::AVProcessor()
    : running_(false)
    , should_stop_(false)
    , sws_ctx_(nullptr)
    , swr_ctx_(nullptr)
{
}

AVProcessor::~AVProcessor() {
    cleanup();
}

AVResult AVProcessor::init(const AVConfig& input_config, const AVConfig& output_config) {
    input_config_ = input_config;
    output_config_ = output_config;

    decoder_ = std::make_unique<AVDecoder>();
    encoder_ = std::make_unique<AVEncoder>();

    return AVResult::Success;
}

void AVProcessor::cleanup() {
    stop();

    if (sws_ctx_) {
        sws_freeContext(sws_ctx_);
        sws_ctx_ = nullptr;
    }

    if (swr_ctx_) {
        swr_free(&swr_ctx_);
        swr_ctx_ = nullptr;
    }

    decoder_.reset();
    encoder_.reset();
}

AVResult AVProcessor::startTranscode(const std::string& input_url, const std::string& output_url) {
    AVResult result = decoder_->open(input_url);
    if (result != AVResult::Success) {
        return result;
    }

    result = encoder_->open(output_config_, output_url);
    if (result != AVResult::Success) {
        decoder_->close();
        return result;
    }

    sws_ctx_ = sws_getContext(
        decoder_->getVideoWidth(), decoder_->getVideoHeight(), AV_PIX_FMT_YUV420P,
        output_config_.video_width, output_config_.video_height, AV_PIX_FMT_YUV420P,
        SWS_BILINEAR, nullptr, nullptr, nullptr
    );

    // 使用新的 FFmpeg 7.0+ API 创建音频重采样器
    swr_alloc(&swr_ctx_);
    av_opt_set_chlayout(swr_ctx_, "in_chlayout", &(AVChannelLayout)AV_CHANNEL_LAYOUT_STEREO, 0);
    av_opt_set_int(swr_ctx_, "in_sample_rate", input_config_.audio_samplerate, 0);
    av_opt_set_sample_fmt(swr_ctx_, "in_sample_fmt", AV_SAMPLE_FMT_S16, 0);

    av_opt_set_chlayout(swr_ctx_, "out_chlayout", &(AVChannelLayout)AV_CHANNEL_LAYOUT_STEREO, 0);
    av_opt_set_int(swr_ctx_, "out_sample_rate", output_config_.audio_samplerate, 0);
    av_opt_set_sample_fmt(swr_ctx_, "out_sample_fmt", AV_SAMPLE_FMT_S16, 0);

    swr_init(swr_ctx_);

    running_ = true;
    should_stop_ = false;

    std::thread(&AVProcessor::processLoop, this).detach();

    return AVResult::Success;
}

void AVProcessor::stop() {
    should_stop_ = true;
    while (running_) {
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }

    if (decoder_) decoder_->close();
    if (encoder_) encoder_->close();
}

void AVProcessor::processLoop() {
    AVResult result;
    int frame_count = 0;
    const int report_interval = 30;

    while (!should_stop_) {
        std::shared_ptr<AVFrameData> frame;
        result = decoder_->readFrame(frame);

        if (result == AVResult::Eof) {
            encoder_->flush();
            break;
        } else if (result != AVResult::Success) {
            break;
        }

        encoder_->writeFrame(frame);

        frame_count++;
        if (progress_callback_ && frame_count % report_interval == 0) {
            double progress = frame_count / (30.0 * 60.0);
            progress_callback_(progress);
        }
    }

    running_ = false;
}

void AVProcessor::applyFilters(AVFrame* frame) {
    // Placeholder for video/audio filters
    // Could implement: watermark, crop, resize, audio normalization, etc.
}

}
