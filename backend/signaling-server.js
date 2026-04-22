// 屏幕共享信令服务器 - Node.js 版本
const WebSocket = require('ws');
const http = require('http');

const HTTP_PORT = 8080;
const WS_PORT = 8081;

// 存储会话信息
const sessions = new Map();
const clients = new Map();

// HTTP 服务器（用于提供静态文件）
const httpServer = http.createServer((req, res) => {
  // 简单的 CORS 处理
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(200);
    res.end();
    return;
  }

  // 健康检查
  if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', sessions: sessions.size }));
    return;
  }

  // 404
  res.writeHead(404);
  res.end('Not Found');
});

// WebSocket 服务器
const wss = new WebSocket.Server({ port: WS_PORT });

wss.on('connection', (ws, req) => {
  const clientId = generateId();
  clients.set(clientId, ws);

  console.log(`[WS] Client connected: ${clientId}`);

  ws.on('message', (message) => {
    try {
      const data = JSON.parse(message);
      console.log(`[WS] ${clientId}: ${data.type}`);

      switch (data.type) {
        case 'create_session':
          handleCreateSession(ws, clientId, data);
          break;

        case 'join_session':
          handleJoinSession(ws, clientId, data);
          break;

        case 'offer':
          handleOffer(ws, clientId, data);
          break;

        case 'answer':
          handleAnswer(ws, clientId, data);
          break;

        case 'ice_candidate':
          handleICECandidate(ws, clientId, data);
          break;
      }

    } catch (error) {
      console.error(`[WS] Error handling message: ${error.message}`);
    }
  });

  ws.on('close', () => {
    console.log(`[WS] Client disconnected: ${clientId}`);
    handleDisconnect(clientId);
    clients.delete(clientId);
  });

  ws.on('error', (error) => {
    console.error(`[WS] Error: ${error.message}`);
  });
});

function handleCreateSession(ws, clientId, data) {
  const sessionId = generateSessionId();

  const session = {
    sessionId,
    hostId: clientId,
    hostWs: ws,
    guestId: null,
    guestWs: null,
    offer: data.offer || null
  };

  sessions.set(sessionId, session);

  // 发送会话 ID 给共享者
  ws.send(JSON.stringify({
    type: 'session_created',
    session_id: sessionId
  }));

  console.log(`[Session] Created: ${sessionId} by ${clientId}`);

  // 如果有 offer，广播给等待中的观看者
  if (session.offer) {
    broadcastOffer(sessionId);
  }
}

function handleJoinSession(ws, clientId, data) {
  const sessionId = data.session_id;
  const session = sessions.get(sessionId);

  if (!session) {
    ws.send(JSON.stringify({
      type: 'error',
      message: 'Session not found'
    }));
    return;
  }

  session.guestId = clientId;
  session.guestWs = ws;

  // 如果有 offer，立即发送给观看者
  if (session.offer) {
    ws.send(JSON.stringify({
      type: 'offer',
      offer: session.offer
    }));
  }

  console.log(`[Session] ${clientId} joined: ${sessionId}`);
}

function handleOffer(ws, clientId, data) {
  const sessionId = data.session_id || getSessionIdByClient(clientId);

  if (!sessionId) return;

  const session = sessions.get(sessionId);
  if (!session) return;

  session.offer = data.offer;
  session.hostId = clientId;
  session.hostWs = ws;

  // 发送 offer 给观看者
  if (session.guestWs && session.guestWs.readyState === WebSocket.OPEN) {
    session.guestWs.send(JSON.stringify({
      type: 'offer',
      offer: data.offer
    }));
    console.log(`[Session] Offer sent to guest`);
  }
}

function handleAnswer(ws, clientId, data) {
  const sessionId = data.session_id;

  if (!sessionId) return;

  const session = sessions.get(sessionId);
  if (!session) return;

  // 发送 answer 给共享者
  if (session.hostWs && session.hostWs.readyState === WebSocket.OPEN) {
    session.hostWs.send(JSON.stringify({
      type: 'answer',
      sdp: data.sdp
    }));
    console.log(`[Session] Answer sent to host`);
  }
}

function handleICECandidate(ws, clientId, data) {
  const sessionId = data.session_id;

  if (!sessionId) return;

  const session = sessions.get(sessionId);
  if (!session) return;

  // 转发 ICE 候选
  const targetWs = (clientId === session.hostId) ? session.guestWs : session.hostWs;

  if (targetWs && targetWs.readyState === WebSocket.OPEN) {
    targetWs.send(JSON.stringify({
      type: 'ice',
      candidate: data.candidate
    }));
    console.log(`[Session] ICE candidate forwarded`);
  }
}

function handleDisconnect(clientId) {
  // 查找并清理相关会话
  for (const [sessionId, session] of sessions.entries()) {
    if (session.hostId === clientId) {
      // 共享者断开，删除整个会话
      sessions.delete(sessionId);
      console.log(`[Session] Removed: ${sessionId}`);
      break;
    } else if (session.guestId === clientId) {
      // 观看者断开
      session.guestId = null;
      session.guestWs = null;
      console.log(`[Session] Guest disconnected from ${sessionId}`);
    }
  }
}

function broadcastOffer(sessionId) {
  const session = sessions.get(sessionId);
  if (!session || !session.offer) return;

  // 发送给等待中的观看者（简化处理）
  console.log(`[Session] Broadcasting offer for ${sessionId}`);
}

function generateId() {
  return Math.random().toString(36).substring(2, 15);
}

function generateSessionId() {
  return 'sess_' + Math.random().toString(36).substring(2, 8);
}

function getSessionIdByClient(clientId) {
  for (const [sessionId, session] of sessions.entries()) {
    if (session.hostId === clientId || session.guestId === clientId) {
      return sessionId;
    }
  }
  return null;
}

// 启动服务器
httpServer.listen(HTTP_PORT, () => {
  console.log('========================================');
  console.log('   Screen Share Signaling Server');
  console.log('========================================');
  console.log('');
  console.log(`HTTP Server: http://localhost:${HTTP_PORT}`);
  console.log(`WebSocket Server: ws://localhost:${WS_PORT}`);
  console.log('');
  console.log('Press Ctrl+C to stop');
  console.log('========================================');
  console.log('');
});

// 优雅关闭
process.on('SIGINT', () => {
  console.log('\nShutting down...');
  wss.close();
  httpServer.close();
  process.exit(0);
});
