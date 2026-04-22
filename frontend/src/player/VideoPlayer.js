import Hls from 'hls.js';
import dashjs from 'dashjs';
import flvjs from 'flv.js';

export class VideoPlayer {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.videoElement = null;
    this.hls = null;
    this.dash = null;
    this.flv = null;
    this.currentType = null;

    this.init();
  }

  init() {
    this.container.innerHTML = '';

    this.videoElement = document.createElement('video');
    this.videoElement.controls = true;
    this.videoElement.autoplay = false;
    this.videoElement.style.width = '100%';
    this.videoElement.style.height = '100%';

    this.container.appendChild(this.videoElement);
  }

  load(url, type = 'auto') {
    this.destroy();

    if (type === 'auto') {
      type = this.detectType(url);
    }

    this.currentType = type;

    switch (type) {
      case 'hls':
        this.loadHLS(url);
        break;
      case 'dash':
        this.loadDASH(url);
        break;
      case 'flv':
        this.loadFLV(url);
        break;
      default:
        this.loadNative(url);
    }
  }

  detectType(url) {
    if (url.includes('.m3u8') || url.includes('m3u8')) {
      return 'hls';
    } else if (url.includes('.mpd') || url.includes('dash')) {
      return 'dash';
    } else if (url.includes('.flv') || url.includes('flv')) {
      return 'flv';
    }
    return 'native';
  }

  loadHLS(url) {
    if (Hls.isSupported()) {
      this.hls = new Hls({
        debug: false,
        enableWorker: true,
        lowLatencyMode: true,
        backBufferLength: 90
      });

      this.hls.loadSource(url);
      this.hls.attachMedia(this.videoElement);

      this.hls.on(Hls.Events.MANIFEST_PARSED, () => {
        console.log('HLS manifest loaded');
      });

      this.hls.on(Hls.Events.ERROR, (event, data) => {
        if (data.fatal) {
          switch (data.type) {
            case Hls.ErrorTypes.NETWORK_ERROR:
              this.hls.startLoad();
              break;
            case Hls.ErrorTypes.MEDIA_ERROR:
              this.hls.recoverMediaError();
              break;
            default:
              this.hls.destroy();
              break;
          }
        }
      });

    } else if (this.videoElement.canPlayType('application/vnd.apple.mpegurl')) {
      this.videoElement.src = url;
    }
  }

  loadDASH(url) {
    this.dash = dashjs.MediaPlayer().create();

    this.dash.initialize(this.videoElement, url, false);

    this.dash.on(dashjs.MediaPlayer.events.STREAM_INITIALIZED, () => {
      console.log('DASH stream initialized');
    });

    this.dash.updateSettings({
      streaming: {
        lowLatencyEnabled: true,
        liveDelay: 3
      }
    });
  }

  loadFLV(url) {
    if (flvjs.isSupported()) {
      this.flv = flvjs.createPlayer({
        type: 'flv',
        url: url,
        isLive: true,
        hasAudio: true,
        hasVideo: true
      });

      this.flv.attachMediaElement(this.videoElement);
      this.flv.load();

      this.flv.on(flvjs.Events.ERROR, (errorType, errorDetail, errorInfo) => {
        console.error('FLV error:', errorType, errorDetail, errorInfo);
      });
    }
  }

  loadNative(url) {
    this.videoElement.src = url;
  }

  play() {
    if (this.videoElement) {
      this.videoElement.play().catch(error => {
        console.error('Play error:', error);
      });
    }
  }

  pause() {
    if (this.videoElement) {
      this.videoElement.pause();
    }
  }

  stop() {
    if (this.videoElement) {
      this.videoElement.pause();
      this.videoElement.currentTime = 0;
    }
  }

  seek(time) {
    if (this.videoElement) {
      this.videoElement.currentTime = time;
    }
  }

  setVolume(volume) {
    if (this.videoElement) {
      this.videoElement.volume = Math.max(0, Math.min(1, volume));
    }
  }

  getVolume() {
    return this.videoElement ? this.videoElement.volume : 1;
  }

  mute() {
    if (this.videoElement) {
      this.videoElement.muted = true;
    }
  }

  unmute() {
    if (this.videoElement) {
      this.videoElement.muted = false;
    }
  }

  isPlaying() {
    return this.videoElement ? !this.videoElement.paused : false;
  }

  getDuration() {
    return this.videoElement ? this.videoElement.duration : 0;
  }

  getCurrentTime() {
    return this.videoElement ? this.videoElement.currentTime : 0;
  }

  destroy() {
    if (this.hls) {
      this.hls.destroy();
      this.hls = null;
    }

    if (this.dash) {
      this.dash.reset();
      this.dash = null;
    }

    if (this.flv) {
      this.flv.destroy();
      this.flv = null;
    }

    if (this.videoElement) {
      this.videoElement.src = '';
      this.videoElement.load();
    }

    this.currentType = null;
  }
}
