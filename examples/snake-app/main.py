#!/usr/bin/env python3
"""
Snake game with persistent leaderboard.
Demonstrates: user input, SQLite writes/reads, multiple API routes.
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import html
import json
import os
import sqlite3

PORT = 8000
DB_PATH = os.environ.get("DB_PATH", "/data/scores.db")


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scores (
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            name  TEXT    NOT NULL,
            score INTEGER NOT NULL,
            ts    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def save_score(name: str, score: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO scores (name, score) VALUES (?, ?)", (name, score))
    conn.commit()
    conn.close()


def get_leaderboard():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT name, score, ts FROM scores ORDER BY score DESC LIMIT 10"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


HOME_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Snake — GatekeeperAI</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:system-ui,sans-serif;background:#0f0f1a;color:#e2e8f0;
         min-height:100vh;display:flex;flex-direction:column;align-items:center;
         justify-content:center;padding:2rem;gap:2rem}
    h1{font-size:2.5rem;font-weight:800;
       background:linear-gradient(135deg,#818cf8,#a78bfa);
       -webkit-background-clip:text;-webkit-text-fill-color:transparent}
    p.sub{color:#94a3b8;margin-top:-1.5rem}
    .card{background:#1e1e2e;border:1px solid #2d2d3f;border-radius:1rem;
          padding:2rem;width:100%;max-width:380px}
    input{width:100%;padding:.75rem 1rem;border-radius:.5rem;
          border:1px solid #3d3d5c;background:#13131f;color:#e2e8f0;
          font-size:1rem;margin-bottom:1rem;outline:none}
    input:focus{border-color:#818cf8}
    button{width:100%;padding:.75rem;border-radius:.5rem;border:none;
           background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;
           font-size:1rem;font-weight:600;cursor:pointer;transition:opacity .2s}
    button:hover{opacity:.88}
    .lb{width:100%;max-width:380px}
    .lb h2{font-size:.8rem;font-weight:600;color:#64748b;text-transform:uppercase;
            letter-spacing:.08em;margin-bottom:.75rem}
    .row{display:flex;justify-content:space-between;align-items:center;
         padding:.45rem 0;border-bottom:1px solid #1a1a2e;font-size:.9rem}
    .rank{color:#6366f1;font-weight:700;width:2rem}
    .nm{flex:1;color:#e2e8f0}
    .sc{color:#a78bfa;font-weight:700}
    .empty{color:#374151;font-size:.9rem;text-align:center;padding:1rem 0}
    .ts{font-size:.75rem;color:#374151;margin-left:.5rem}
  </style>
</head>
<body>
  <h1>🐍 Snake</h1>
  <p class="sub">A GatekeeperAI sample app</p>
  <div class="card">
    <form action="game" method="GET">
      <input name="name" type="text" placeholder="Enter your name" maxlength="30" autofocus required>
      <button type="submit">Play →</button>
    </form>
  </div>
  <div class="lb">
    <h2>🏆 Leaderboard</h2>
    <div id="lb"></div>
  </div>
  <script>
    fetch('api/leaderboard').then(r=>r.json()).then(rows=>{
      const el=document.getElementById('lb');
      if(!rows.length){el.innerHTML='<p class="empty">No scores yet — be the first!</p>';return}
      el.innerHTML=rows.map((r,i)=>`
        <div class="row">
          <span class="rank">#${i+1}</span>
          <span class="nm">${r.name}<span class="ts">${r.ts.slice(0,10)}</span></span>
          <span class="sc">${r.score}</span>
        </div>`).join('');
    });
  </script>
</body>
</html>"""


GAME_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Snake — {{NAME}}</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:system-ui,sans-serif;background:#0f0f1a;color:#e2e8f0;
         min-height:100vh;display:flex;flex-direction:column;align-items:center;
         justify-content:center;gap:.75rem;padding:1rem}
    .hud{display:flex;gap:2rem;font-size:.9rem;color:#64748b}
    .hud b{color:#a78bfa}
    .wrap{position:relative;line-height:0}
    canvas{border:2px solid #2d2d3f;border-radius:.5rem;display:block}
    .overlay{position:absolute;inset:0;background:rgba(10,10,20,.88);
             border-radius:.5rem;display:flex;flex-direction:column;
             align-items:center;justify-content:center;gap:1rem;padding:2rem}
    .overlay h2{font-size:1.4rem;font-weight:800;color:#f87171}
    .big{font-size:2.5rem;font-weight:800;color:#a78bfa}
    .btns{display:flex;gap:.5rem}
    button{padding:.6rem 1.4rem;border-radius:.5rem;border:none;
           background:linear-gradient(135deg,#6366f1,#8b5cf6);color:#fff;
           font-size:.9rem;font-weight:600;cursor:pointer}
    button.sec{background:#1e1e2e;border:1px solid #2d2d3f;color:#94a3b8}
    .hint{font-size:.75rem;color:#374151}
    .lb{width:400px;margin-top:.5rem}
    .lb h3{font-size:.75rem;font-weight:600;color:#64748b;text-transform:uppercase;
            letter-spacing:.08em;margin-bottom:.5rem}
    .row{display:flex;justify-content:space-between;padding:.35rem 0;
         border-bottom:1px solid #1a1a2e;font-size:.85rem}
    .rank{color:#6366f1;font-weight:700;width:2rem}
    .nm{flex:1}
    .sc{color:#a78bfa;font-weight:700}
    .you{color:#4ade80!important;font-weight:700}
    #saving{font-size:.8rem;color:#64748b}
  </style>
</head>
<body>
  <div class="hud">
    <span>Player: <b>{{NAME}}</b></span>
    <span>Score: <b id="score">0</b></span>
    <span>Best: <b id="best">—</b></span>
  </div>
  <div class="wrap">
    <canvas id="c" width="400" height="400"></canvas>
    <div class="overlay" id="ov">
      <div style="font-size:1.1rem;color:#94a3b8">Ready?</div>
      <button onclick="startGame()">Start Game</button>
      <p class="hint">Arrow keys or WASD to steer</p>
    </div>
  </div>
  <div id="lb-wrap" style="display:none" class="lb">
    <h3>🏆 Leaderboard</h3>
    <div id="lb-rows"></div>
  </div>
  <script>
  const NAME = "{{NAME}}";
  const G = 20, C = 20;
  const canvas = document.getElementById('c');
  const ctx = canvas.getContext('2d');
  let snake, dir, nextDir, food, score, loop, alive;

  function rnd(n){return Math.floor(Math.random()*n)}

  function spawnFood(){
    let f;
    do{ f={x:rnd(G),y:rnd(G)} }
    while(snake.some(s=>s.x===f.x&&s.y===f.y));
    return f;
  }

  function init(){
    snake=[{x:10,y:10},{x:9,y:10},{x:8,y:10}];
    dir={x:1,y:0}; nextDir={x:1,y:0};
    food=spawnFood(); score=0; alive=true;
    document.getElementById('score').textContent='0';
  }

  function startGame(){
    document.getElementById('ov').style.display='none';
    document.getElementById('lb-wrap').style.display='none';
    init(); draw();
    clearInterval(loop);
    loop=setInterval(tick,130);
  }

  function tick(){
    dir=nextDir;
    const h={x:snake[0].x+dir.x, y:snake[0].y+dir.y};
    if(h.x<0||h.x>=G||h.y<0||h.y>=G||snake.some(s=>s.x===h.x&&s.y===h.y)){
      clearInterval(loop); gameOver(); return;
    }
    snake.unshift(h);
    if(h.x===food.x&&h.y===food.y){
      score+=10;
      document.getElementById('score').textContent=score;
      food=spawnFood();
      if(score%50===0){ clearInterval(loop); loop=setInterval(tick,Math.max(55,130-score*.8)); }
    } else { snake.pop(); }
    draw();
  }

  function draw(){
    ctx.fillStyle='#0a0a14';
    ctx.fillRect(0,0,400,400);
    // grid dots
    ctx.fillStyle='#161626';
    for(let x=0;x<G;x++) for(let y=0;y<G;y++) ctx.fillRect(x*C+9,y*C+9,2,2);
    // food (pulsing red circle)
    ctx.fillStyle='#f87171';
    ctx.shadowBlur=12; ctx.shadowColor='#f87171';
    ctx.beginPath();
    ctx.arc(food.x*C+C/2,food.y*C+C/2,C/2-3,0,Math.PI*2);
    ctx.fill();
    ctx.shadowBlur=0;
    // snake
    snake.forEach((s,i)=>{
      const t=i/snake.length;
      ctx.fillStyle=i===0?'#818cf8':`rgba(139,92,246,${1-t*.6})`;
      if(i===0){ctx.shadowBlur=10;ctx.shadowColor='#818cf8';}
      else{ctx.shadowBlur=0;}
      ctx.beginPath();
      ctx.roundRect(s.x*C+1,s.y*C+1,C-2,C-2,i===0?5:3);
      ctx.fill();
    });
    ctx.shadowBlur=0;
  }

  async function gameOver(){
    // Show overlay immediately
    const ov=document.getElementById('ov');
    ov.innerHTML=`<h2>Game Over</h2><div class="big">${score} pts</div>
      <p id="saving">Saving score...</p>
      <div class="btns">
        <button onclick="startGame()">Play Again</button>
        <button class="sec" onclick="location.href='./'">Home</button>
      </div>`;
    ov.style.display='flex';

    // Save to DB
    try{
      await fetch('api/score',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name:NAME,score})
      });
      document.getElementById('saving').textContent='Score saved ✓';
    } catch(e){
      document.getElementById('saving').textContent='(could not save score)';
    }

    // Update best
    const bestEl=document.getElementById('best');
    const prev=parseInt(bestEl.textContent)||0;
    if(score>prev) bestEl.textContent=score;

    // Load leaderboard
    const rows=await fetch('api/leaderboard').then(r=>r.json());
    const el=document.getElementById('lb-rows');
    el.innerHTML=rows.map((r,i)=>`
      <div class="row">
        <span class="rank">#${i+1}</span>
        <span class="nm ${r.name===NAME&&r.score===score?'you':''}">${r.name}</span>
        <span class="sc">${r.score}</span>
      </div>`).join('');
    document.getElementById('lb-wrap').style.display='block';
  }

  // Controls
  const KEYS={
    ArrowUp:{x:0,y:-1},ArrowDown:{x:0,y:1},ArrowLeft:{x:-1,y:0},ArrowRight:{x:1,y:0},
    w:{x:0,y:-1},s:{x:0,y:1},a:{x:-1,y:0},d:{x:1,y:0},
    W:{x:0,y:-1},S:{x:0,y:1},A:{x:-1,y:0},D:{x:1,y:0}
  };
  document.addEventListener('keydown',e=>{
    const d=KEYS[e.key];
    if(d&&alive&&!(d.x===-dir.x&&d.y===-dir.y)){
      nextDir=d; e.preventDefault();
    }
  });

  // Init draw + load best
  init(); draw();
  fetch('api/leaderboard').then(r=>r.json()).then(rows=>{
    if(rows.length) document.getElementById('best').textContent=rows[0].score;
  });
  </script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}", flush=True)

    def do_GET(self):
        p = urlparse(self.path)
        qs = parse_qs(p.query)
        if p.path == "/":
            self._ok("text/html", HOME_HTML)
        elif p.path == "/game":
            name = html.escape(qs.get("name", ["Player"])[0][:30])
            self._ok("text/html", GAME_HTML.replace("{{NAME}}", name))
        elif p.path == "/api/leaderboard":
            self._ok("application/json", json.dumps(get_leaderboard()))
        elif p.path == "/health":
            self._ok("application/json", json.dumps({"status": "ok"}))
        else:
            self._send(404, "text/plain", "Not found")

    def do_POST(self):
        if self.path == "/api/score":
            try:
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n))
                name = html.escape(str(body.get("name", ""))[:30])
                score = max(0, int(body.get("score", 0)))
                save_score(name, score)
                self._ok("application/json", json.dumps({"ok": True}))
            except Exception as e:
                self._send(400, "application/json", json.dumps({"error": str(e)}))
        else:
            self._send(404, "text/plain", "Not found")

    def _ok(self, ct, body):
        self._send(200, ct, body)

    def _send(self, status, ct, body):
        enc = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(enc)))
        self.end_headers()
        self.wfile.write(enc)


if __name__ == "__main__":
    init_db()
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Snake server listening on port {PORT}", flush=True)
    server.serve_forever()
