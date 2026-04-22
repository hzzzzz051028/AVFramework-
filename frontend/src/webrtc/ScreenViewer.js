// 屏幕共享观看端客户端
export class ScreenViewer {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.ws = null;
    this.pc = null;
    remoteStream = null;
    this.sessionId = null;
    this.isConnected = false;

    this.config = {
      iceServers: [
        { urls: 'stun:stun.l.google.com:19302' }
      ]
    };
  }

  async connect() {
    return new Promise((resolve, reject) => {
      this.ws = new WebSocket(this.wsUrl);

      this.ws.onopen = () => {
        console.log('✅ Viewer WebSocket connected');
        this.setupMessageHandler();
        resolve();
      };

      this.ws.onerror = (error) => {
        console.error('❌ Viewer WebSocket connection failed');
        reject(new Error('WebSocket connection failed'));
      };

      this.ws.onclose = () => {
        console.log('🔌 Viewer WebSocket disconnected');
      };
    });
  }

  setupMessageHandler() {
    this.ws.onmessage = async (event) => {
      try {
        const message = JSON.parse(event.data);
        console.log('📨 Viewer received:', message.type);

        switch (message.type) {
          case 'session_created':
            this.sessionId = message.session_id;
            console.log('🎫 Session created:', this.sessionId);
            this.onSessionCreated?.(this.sessionId);
            break;

          case 'offer':
            await this.handleOffer(message.offer);
            break;

          case 'answer':
            await this.handleAnswer(message.sdp);
            break;

          case 'ice':
            await this.handleICECandidate(message.candidate);
            break;
        }

      } catch (error) {
        console.error('Message handling error:', error);
      }
    };
  }

  async joinSession(sessionId) {
    this.sessionId = sessionId;
    this.createPeerConnection();

    this.send({
      type: 'join_session',
      session_id: sessionId
    });
  }

  createPeerConnection() {
    this.pc = new RTCPeerConnection(this.config);

    this.pc.onicecandidate = (event) => {
      if (event.candidate) {
        this.send({
          type: 'ice_candidate',
          session_id: this.sessionId,
          candidate: JSON.stringify(event.candidate)
        });
      }
    };

    this.pc.ontrack = (event) => {
      console.log('📹 Received screen share track');
      const [remoteStream] = event.streams;
      this.remoteStream = remoteStream;
      this.onRemoteStream?.(remoteStream);
    };

    this.pc.onconnectionstatechange = () => {
      console.log('🔄 Connection state:', this.pc.connectionState);
      this.isConnected = (this.pc.connectionState === 'connected');
      this.onStateChange?.(this.pc.connectionState);
    };
  }

  async handleOffer(sdpString) {
    if (!this.pc) {
      this.createPeerConnection();
    }

    const offer = JSON.parse(sdpString);
    await this.pc.setRemoteDescription(new RTCSessionDescription(offer));

    const answer = await this.pc.createAnswer();
    await this.pc.setLocalDescription(answer);

    this.send({
      type: 'answer',
      session_id: this.sessionId,
      sdp: JSON.stringify(answer)
    });
  }

  async handleAnswer(sdpString) {
    const answer = JSON.parse(sdpString);
    await this.pc.setRemoteDescription(new RTCSessionDescription(answer));
  }

  async handleICECandidate(candidateString) {
    const candidate = JSON.parse(candidateString);
    await this.pc.addIceCandidate(new RTCIceCandidate(candidate));
  }

  send(message) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    }
  }

  disconnect() {
    console.log('🛑 Disconnecting viewer');

    if (this.pc) {
      this.pc.close();
      this.pc = null;
    }

    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }

    this.isConnected = false;
  }

  // 回调函数
  onSessionCreated = null;
  onRemoteStream = null;
  onStateChange = null;
}
