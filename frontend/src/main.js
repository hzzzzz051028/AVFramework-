import { VideoPlayer } from './player/VideoPlayer.js';
import { WebRTCClient } from './webrtc/WebRTCClient.js';
import { API } from './services/API.js';

class App {
  constructor() {
    this.currentSection = 'player';
    this.player = null;
    this.webrtcClient = null;
    this.api = new API('http://localhost:8080');

    this.init();
  }

  init() {
    this.setupNavigation();
    this.setupPlayer();
    this.setupStreams();
    this.setupWebRTC();
    this.setupUpload();
  }

  setupNavigation() {
    const navButtons = document.querySelectorAll('nav button');
    const sections = document.querySelectorAll('.section');

    navButtons.forEach(button => {
      button.addEventListener('click', () => {
        const section = button.dataset.section;

        navButtons.forEach(btn => btn.classList.remove('active'));
        button.classList.add('active');

        sections.forEach(sec => sec.classList.remove('active'));
        document.getElementById(`${section}-section`).classList.add('active');

        this.currentSection = section;

        if (section === 'streams') {
          this.loadStreams();
        }
      });
    });
  }

  setupPlayer() {
    this.player = new VideoPlayer('player-container');

    document.getElementById('play-btn').addEventListener('click', () => {
      const url = document.getElementById('stream-url').value;
      const type = document.getElementById('stream-type').value;

      if (url) {
        this.player.load(url, type);
      }
    });

    document.getElementById('stop-btn').addEventListener('click', () => {
      this.player.stop();
    });
  }

  setupStreams() {
    document.getElementById('refresh-streams').addEventListener('click', () => {
      this.loadStreams();
    });

    document.getElementById('create-stream').addEventListener('click', () => {
      this.createStream();
    });
  }

  async loadStreams() {
    const listContainer = document.getElementById('stream-list');
    listContainer.innerHTML = '<div class="loading"></div>';

    try {
      const streams = await this.api.getStreams();

      if (streams.length === 0) {
        listContainer.innerHTML = '<p style="color: rgba(255,255,255,0.5);">暂无流</p>';
        return;
      }

      listContainer.innerHTML = streams.map(stream => `
        <div class="stream-item" data-id="${stream.id}">
          <h3>
            <span class="status ${stream.active ? 'online' : 'offline'}"></span>
            ${stream.id}
          </h3>
          <p>${stream.width}x${stream.height} @ ${stream.fps}fps</p>
          <p>${stream.active ? '在线' : '离线'}</p>
        </div>
      `).join('');

      listContainer.querySelectorAll('.stream-item').forEach(item => {
        item.addEventListener('click', () => {
          const streamId = item.dataset.id;
          const url = `http://localhost:8080/hls/${streamId}/stream.m3u8`;

          document.getElementById('stream-url').value = url;
          document.getElementById('stream-type').value = 'hls';

          document.querySelector('nav button[data-section="player"]').click();
        });
      });

    } catch (error) {
      listContainer.innerHTML = '<p style="color: #ef4444;">加载失败: ' + error.message + '</p>';
    }
  }

  async createStream() {
    const streamId = prompt('请输入流ID:', 'stream_' + Date.now());

    if (!streamId) return;

    try {
      const result = await this.api.createStream(streamId, {
        width: 1920,
        height: 1080,
        fps: 30
      });

      alert('流创建成功!\n流地址: ' + result.stream_url);
      this.loadStreams();

    } catch (error) {
      alert('创建失败: ' + error.message);
    }
  }

  setupWebRTC() {
    this.webrtcClient = new WebRTCClient('ws://localhost:8081');

    document.getElementById('start-webrtc').addEventListener('click', async () => {
      try {
        await this.webrtcClient.start();

        document.getElementById('local-video').srcObject =
          this.webrtcClient.localStream;

        this.webrtcClient.on('track', (event) => {
          const [remoteStream] = event.streams;
          document.getElementById('remote-video').srcObject = remoteStream;
        });

        await this.webrtcClient.createOffer();

      } catch (error) {
        alert('启动失败: ' + error.message);
      }
    });

    document.getElementById('stop-webrtc').addEventListener('click', () => {
      this.webrtcClient.stop();
      document.getElementById('local-video').srcObject = null;
      document.getElementById('remote-video').srcObject = null;
    });

    document.getElementById('toggle-mic').addEventListener('click', (e) => {
      if (this.webrtcClient.localStream) {
        const audioTrack = this.webrtcClient.localStream.getAudioTracks()[0];
        if (audioTrack) {
          audioTrack.enabled = !audioTrack.enabled;
          e.target.textContent = audioTrack.enabled ? '静音麦克风' : '取消静音';
        }
      }
    });

    document.getElementById('toggle-camera').addEventListener('click', (e) => {
      if (this.webrtcClient.localStream) {
        const videoTrack = this.webrtcClient.localStream.getVideoTracks()[0];
        if (videoTrack) {
          videoTrack.enabled = !videoTrack.enabled;
          e.target.textContent = videoTrack.enabled ? '关闭摄像头' : '开启摄像头';
        }
      }
    });
  }

  setupUpload() {
    document.getElementById('upload-btn').addEventListener('click', async () => {
      const fileInput = document.getElementById('video-file');
      const file = fileInput.files[0];

      if (!file) {
        alert('请选择视频文件');
        return;
      }

      const progressDiv = document.getElementById('upload-progress');
      const progressBar = document.getElementById('progress-bar');
      const progressText = document.getElementById('progress-text');

      progressDiv.style.display = 'block';
      progressBar.style.width = '0%';
      progressText.textContent = '0%';

      try {
        await this.api.uploadVideo(file, (progress) => {
          progressBar.style.width = progress + '%';
          progressText.textContent = progress + '%';
        });

        alert('上传成功!');
        progressDiv.style.display = 'none';
        fileInput.value = '';

      } catch (error) {
        alert('上传失败: ' + error.message);
        progressDiv.style.display = 'none';
      }
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  new App();
});
