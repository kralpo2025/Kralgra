import sqlite3
import json
import os
import uuid
import time
from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import aiofiles
import uvicorn

app = FastAPI()

# --- Config & Setup ---
DB_NAME = "kralgram.db"
UPLOAD_DIR = "static/uploads"

# Ensure directories exist BEFORE mounting
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Mount static files for uploads
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- HTML Content ---
html_content = """
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>KRALGRAM | کرال‌گرام</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@100;300;400;700&display=swap');
        
        * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }

        body {
            font-family: 'Vazirmatn', sans-serif;
            background: linear-gradient(45deg, #0f0c29, #302b63, #24243e);
            background-size: 400% 400%;
            animation: gradientBG 15s ease infinite;
            height: 100vh;
            height: 100dvh; /* Mobile fix */
            overflow: hidden;
            color: white;
            margin: 0;
            padding: 0;
        }

        @keyframes gradientBG {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        /* Glassmorphism */
        .glass {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .glass-panel {
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
        }

        .glass-input {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.1);
            color: white;
        }
        .glass-input:focus {
            outline: none;
            border-color: #4facfe;
            background: rgba(0, 0, 0, 0.5);
        }

        .msg-bubble {
            max-width: 85%;
            word-wrap: break-word;
            position: relative;
        }
        
        .msg-sent {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 16px 16px 0 16px;
        }
        
        .msg-received {
            background: rgba(255, 255, 255, 0.15);
            border-radius: 16px 16px 16px 0;
        }

        /* Mobile Optimization */
        .mobile-screen {
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            transition: transform 0.3s ease-in-out;
            background: transparent;
        }

        .show-chat .mobile-sidebar { transform: translateX(100%); } /* Hide sidebar to right */
        .show-chat .mobile-chat { transform: translateX(0); }
        
        /* Sidebar visible by default */
        .mobile-sidebar { z-index: 20; background: rgba(15, 12, 41, 0.95); backdrop-filter: blur(10px); }
        /* Chat hidden to left by default */
        .mobile-chat { transform: translateX(-100%); z-index: 30; background: #1a1a2e; }

        @media (min-width: 768px) {
            .mobile-sidebar { position: relative; transform: none !important; width: 30%; background: transparent; }
            .mobile-chat { position: relative; transform: none !important; width: 70%; background: transparent; }
            .back-btn { display: none; }
        }

        /* Scrollbar */
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 10px; }

        .hidden-page { display: none !important; }
        .fade-in { animation: fadeIn 0.4s ease-in-out; }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
    </style>
</head>
<body class="flex items-center justify-center">

    <!-- Auth Page -->
    <div id="authPage" class="w-full max-w-md p-6 glass glass-panel rounded-2xl fade-in m-4 flex flex-col justify-center" style="min-height: 50vh;">
        <div class="text-center mb-8">
            <h1 class="text-5xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500 mb-2 drop-shadow-lg">KRALGRAM</h1>
            <p class="text-gray-400 text-sm tracking-widest">ارتباط بدون مرز</p>
        </div>

        <div class="flex mb-6 glass rounded-xl p-1">
            <button onclick="toggleAuth('login')" id="tab-login" class="flex-1 py-3 rounded-lg bg-white/10 transition font-bold text-sm">ورود</button>
            <button onclick="toggleAuth('register')" id="tab-register" class="flex-1 py-3 rounded-lg transition text-gray-400 font-bold text-sm">ثبت نام</button>
        </div>

        <form id="loginForm" class="space-y-4">
            <input type="text" id="l_username" placeholder="نام کاربری" class="w-full p-4 rounded-xl glass-input placeholder-gray-400 text-left" dir="ltr">
            <input type="password" id="l_password" placeholder="رمز عبور" class="w-full p-4 rounded-xl glass-input placeholder-gray-400 text-left" dir="ltr">
            <button type="submit" class="w-full py-4 rounded-xl bg-gradient-to-r from-blue-600 to-purple-700 font-bold shadow-lg shadow-blue-900/50 text-white active:scale-95 transition">ورود به حساب</button>
        </form>

        <form id="registerForm" class="space-y-4 hidden-page">
            <input type="text" id="r_name" placeholder="نام نمایشی (مثلا: علی)" class="w-full p-4 rounded-xl glass-input placeholder-gray-400">
            <input type="text" id="r_username" placeholder="نام کاربری (انگلیسی)" class="w-full p-4 rounded-xl glass-input placeholder-gray-400 text-left" dir="ltr">
            <input type="password" id="r_password" placeholder="رمز عبور" class="w-full p-4 rounded-xl glass-input placeholder-gray-400 text-left" dir="ltr">
            <button type="submit" class="w-full py-4 rounded-xl bg-gradient-to-r from-purple-600 to-pink-700 font-bold shadow-lg shadow-purple-900/50 text-white active:scale-95 transition">ساخت حساب</button>
        </form>
    </div>

    <!-- Main App Container -->
    <div id="mainApp" class="hidden-page w-full h-full md:h-[90vh] md:w-[95vw] md:max-w-6xl md:glass md:glass-panel md:rounded-3xl flex overflow-hidden relative">
        
        <!-- Sidebar (User List) -->
        <div class="mobile-sidebar mobile-screen flex flex-col h-full border-l border-white/5" id="sidebarPanel">
            <!-- Header -->
            <div class="p-4 glass border-b border-white/5 flex justify-between items-center z-10">
                <div class="flex items-center gap-3">
                    <div class="w-11 h-11 rounded-full bg-gradient-to-br from-yellow-400 to-orange-600 flex items-center justify-center text-lg font-bold shadow-inner" id="myAvatar">U</div>
                    <div class="flex flex-col">
                        <h3 class="font-bold text-lg leading-tight" id="myName">کاربر</h3>
                        <span class="text-[10px] text-green-400 flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse"></span> آنلاین</span>
                    </div>
                </div>
                <button onclick="toggleGroupTools()" class="w-10 h-10 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center transition"><i class="fas fa-plus text-lg"></i></button>
            </div>

            <!-- Create/Join Group Panel -->
            <div id="groupTools" class="p-4 bg-black/40 backdrop-blur-md hidden border-b border-white/10 transition-all">
                <p class="text-xs text-gray-400 mb-2">مدیریت گروه‌ها</p>
                <div class="flex gap-2 mb-3">
                    <input type="text" id="groupNameInp" placeholder="نام گروه جدید" class="flex-1 p-2 rounded-lg glass-input text-sm">
                    <button onclick="createGroup()" class="bg-blue-600 px-3 rounded-lg text-sm whitespace-nowrap">ایجاد</button>
                </div>
                <div class="w-full h-px bg-white/10 my-2"></div>
                <div class="flex gap-2">
                    <input type="text" id="inviteLinkInp" placeholder="لینک دعوت" class="flex-1 p-2 rounded-lg glass-input text-sm text-left" dir="ltr">
                    <button onclick="joinGroup()" class="bg-green-600 px-3 rounded-lg text-sm whitespace-nowrap">عضویت</button>
                </div>
            </div>

            <!-- Chat List -->
            <div class="flex-1 overflow-y-auto p-2 space-y-1" id="chatList">
                <!-- Items injected via JS -->
            </div>
        </div>

        <!-- Chat Area -->
        <div class="mobile-chat mobile-screen flex flex-col h-full bg-[#0b0b14]/80 backdrop-blur-sm" id="chatPanel">
            
            <!-- Default Placeholder -->
            <div id="emptyState" class="absolute inset-0 flex flex-col items-center justify-center text-center p-8 z-0 hidden md:flex">
                <div class="w-24 h-24 bg-gradient-to-tr from-blue-500/20 to-purple-500/20 rounded-full flex items-center justify-center mb-4 animate-pulse">
                    <i class="fas fa-comments text-4xl text-white/50"></i>
                </div>
                <p class="text-gray-400">یک گفتگو را انتخاب کنید</p>
            </div>

            <!-- Chat Header -->
            <div class="p-3 glass border-b border-white/5 flex items-center gap-3 z-10 shrink-0 shadow-sm">
                <button onclick="backToSidebar()" class="back-btn w-10 h-10 rounded-full active:bg-white/10 flex items-center justify-center text-gray-300">
                    <i class="fas fa-arrow-right"></i>
                </button>
                <div class="w-10 h-10 rounded-full bg-gray-600 flex items-center justify-center font-bold text-sm shadow-lg" id="chatHeaderAvatar">?</div>
                <div class="flex-1 overflow-hidden">
                    <h3 class="font-bold truncate" id="chatHeaderName">...</h3>
                    <p class="text-xs text-blue-300 truncate" id="chatHeaderInfo">...</p>
                </div>
            </div>

            <!-- Messages -->
            <div class="flex-1 overflow-y-auto p-4 space-y-3 relative" id="messagesList">
                <!-- Msgs injected here -->
            </div>

            <!-- Input Bar -->
            <div class="p-2 glass shrink-0 z-20">
                <div class="flex items-end gap-2 bg-black/30 p-1.5 rounded-3xl border border-white/5">
                    
                    <button onclick="document.getElementById('fileInput').click()" class="w-10 h-10 rounded-full text-gray-400 hover:text-white hover:bg-white/10 flex items-center justify-center transition shrink-0">
                        <i class="fas fa-paperclip text-lg"></i>
                    </button>
                    <input type="file" id="fileInput" class="hidden" onchange="uploadFile(this.files[0])">
                    
                    <textarea id="msgInput" rows="1" placeholder="پیام..." class="flex-1 bg-transparent p-2.5 text-white focus:outline-none resize-none overflow-hidden max-h-32 text-sm leading-6" style="min-height: 44px;"></textarea>
                    
                    <button id="voiceBtn" class="w-10 h-10 rounded-full text-gray-400 hover:text-red-400 hover:bg-white/10 flex items-center justify-center transition shrink-0" 
                        onmousedown="startRecording()" onmouseup="stopRecording()" 
                        ontouchstart="startRecording()" ontouchend="stopRecording()">
                        <i class="fas fa-microphone text-lg"></i>
                    </button>

                    <button onclick="sendText()" class="w-11 h-11 rounded-full bg-blue-600 text-white flex items-center justify-center shadow-lg shadow-blue-600/30 transform active:scale-90 transition shrink-0">
                        <i class="fas fa-paper-plane text-sm translate-x-px translate-y-px"></i>
                    </button>
                </div>
            </div>
        </div>
    </div>

    <!-- Toast Notification -->
    <div id="toast" class="fixed top-6 left-1/2 transform -translate-x-1/2 glass px-5 py-3 rounded-2xl shadow-2xl transition-all duration-300 opacity-0 pointer-events-none z-50 flex items-center gap-3 min-w-[200px] justify-center border border-white/20">
        <i class="fas fa-bell text-yellow-400"></i>
        <span id="toastMsg" class="font-bold text-sm">پیام سیستم</span>
    </div>

    <script>
        // --- Core Variables ---
        let user = JSON.parse(localStorage.getItem('kral_user')) || null;
        let ws = null;
        let currentChat = null; 
        let mediaRecorder = null;
        let audioChunks = [];

        // --- UI Functions ---
        function toggleAuth(type) {
            const loginForm = document.getElementById('loginForm');
            const registerForm = document.getElementById('registerForm');
            const tabLogin = document.getElementById('tab-login');
            const tabRegister = document.getElementById('tab-register');

            if(type === 'login') {
                loginForm.classList.remove('hidden-page');
                registerForm.classList.add('hidden-page');
                tabLogin.classList.replace('text-gray-400', 'text-white');
                tabLogin.classList.add('bg-white/10');
                tabRegister.classList.add('text-gray-400');
                tabRegister.classList.remove('bg-white/10');
            } else {
                loginForm.classList.add('hidden-page');
                registerForm.classList.remove('hidden-page');
                tabRegister.classList.replace('text-gray-400', 'text-white');
                tabRegister.classList.add('bg-white/10');
                tabLogin.classList.add('text-gray-400');
                tabLogin.classList.remove('bg-white/10');
            }
        }

        function showToast(msg) {
            const t = document.getElementById('toast');
            document.getElementById('toastMsg').innerText = msg;
            t.classList.remove('opacity-0', '-translate-y-4');
            setTimeout(() => t.classList.add('opacity-0', '-translate-y-4'), 3000);
        }

        function toggleGroupTools() {
            document.getElementById('groupTools').classList.toggle('hidden');
        }

        // --- Mobile Navigation ---
        function openMobileChat() {
            document.getElementById('mainApp').classList.add('show-chat');
        }
        function backToSidebar() {
            document.getElementById('mainApp').classList.remove('show-chat');
            currentChat = null; // Deselect
        }

        // --- Initialization ---
        if (user) {
            initApp();
        } else {
            document.getElementById('authPage').style.display = 'flex';
        }

        // --- API & Logic ---
        document.getElementById('loginForm').onsubmit = async (e) => {
            e.preventDefault();
            const u = document.getElementById('l_username').value;
            const p = document.getElementById('l_password').value;
            try {
                const res = await fetch('/api/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: u, password: p})
                });
                const data = await res.json();
                if(res.ok) {
                    localStorage.setItem('kral_user', JSON.stringify(data));
                    user = data;
                    initApp();
                } else showToast(data.error);
            } catch(e) { showToast("خطا در ارتباط"); }
        };

        document.getElementById('registerForm').onsubmit = async (e) => {
            e.preventDefault();
            const n = document.getElementById('r_name').value;
            const u = document.getElementById('r_username').value;
            const p = document.getElementById('r_password').value;
            try {
                const res = await fetch('/api/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({name: n, username: u, password: p})
                });
                const data = await res.json();
                if(res.ok) {
                    user = data;
                    localStorage.setItem('kral_user', JSON.stringify(data));
                    initApp();
                } else showToast(data.error);
            } catch(e) { showToast("خطا در ارتباط"); }
        };

        function initApp() {
            document.getElementById('authPage').classList.add('hidden-page');
            document.getElementById('mainApp').classList.remove('hidden-page');
            document.getElementById('mainApp').classList.add('fade-in');
            
            document.getElementById('myName').innerText = user.name;
            document.getElementById('myAvatar').innerText = user.name[0];

            connectWS();
            loadChats();
        }

        function connectWS() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const host = window.location.host;
            ws = new WebSocket(`${protocol}//${host}/ws/${user.id}`);
            
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.action === "new_message") {
                    handleNewMessage(data);
                } else if (data.action === "status_update") {
                    updateMessageStatus(data.msg_id, data.status);
                }
            };
            ws.onclose = () => setTimeout(connectWS, 3000);
        }

        async function loadChats() {
            const res = await fetch(`/api/my_chats/${user.id}`);
            const data = await res.json();
            const list = document.getElementById('chatList');
            list.innerHTML = "";

            // Groups
            data.groups.forEach(g => {
                list.innerHTML += chatItemHTML(g.id, g.name, 'group');
            });

            // Users (PVs)
            data.users.forEach(u => {
                list.innerHTML += chatItemHTML(u.id, u.name, 'pv');
            });
        }

        function chatItemHTML(id, name, type) {
            const icon = type === 'group' ? 'users' : 'user';
            const color = type === 'group' ? 'bg-indigo-600' : 'bg-pink-600';
            const sub = type === 'group' ? 'گروه' : 'پیام شخصی';
            return `
            <div onclick="openChat('${id}', '${name}', '${type}')" class="p-3 rounded-2xl hover:bg-white/10 cursor-pointer transition flex items-center gap-3 group active:scale-95 duration-150">
                <div class="w-12 h-12 rounded-full ${color} flex items-center justify-center shadow-lg group-hover:scale-110 transition">
                    <i class="fas fa-${icon}"></i>
                </div>
                <div class="flex-1 min-w-0">
                    <h4 class="font-bold text-sm truncate">${name}</h4>
                    <p class="text-xs text-gray-400 truncate opacity-70 group-hover:opacity-100">${sub}</p>
                </div>
                <i class="fas fa-chevron-left text-xs text-gray-600 opacity-0 group-hover:opacity-100 transition"></i>
            </div>`;
        }

        // --- Chat Functions ---
        async function openChat(id, name, type) {
            currentChat = {id, name, type};
            openMobileChat();
            
            document.getElementById('chatHeaderName').innerText = name;
            document.getElementById('chatHeaderAvatar').innerText = name[0];
            document.getElementById('chatHeaderInfo').innerText = type === 'group' ? 'گروه' : 'آنلاین';

            // Load logic
            let loadId = id;
            if (type === 'pv') {
                const ids = [user.id, id].sort();
                loadId = `${ids[0]}_${ids[1]}`;
            }

            const list = document.getElementById('messagesList');
            list.innerHTML = '<div class="flex justify-center mt-10"><div class="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div></div>'; // Loader

            const res = await fetch(`/api/messages/${loadId}`);
            const msgs = await res.json();
            list.innerHTML = "";
            msgs.forEach(m => renderMessage(m));
            scrollToBottom();
        }

        function renderMessage(msg) {
            const isMe = msg.sender_id === user.id;
            const align = isMe ? 'justify-end' : 'justify-start';
            const bg = isMe ? 'msg-sent' : 'msg-received';
            const tickColor = msg.status === 'seen' ? 'text-blue-300' : 'text-gray-300';
            const tickIcon = msg.status === 'seen' ? 'fa-check-double' : 'fa-check';
            const tick = isMe ? `<i class="fas ${tickIcon} ${tickColor} text-[10px]"></i>` : '';
            
            if (!isMe && msg.status !== 'seen' && ws && currentChat) {
                 ws.send(JSON.stringify({ action: 'read', msg_id: msg.id, sender_id: msg.sender_id }));
            }

            let contentHTML = '';
            if(msg.msg_type === 'text') contentHTML = `<p class="leading-relaxed text-sm">${msg.content}</p>`;
            else if(msg.msg_type === 'image') contentHTML = `<img src="${msg.content}" class="rounded-lg max-h-64 object-cover cursor-pointer" onclick="window.open(this.src)">`;
            else if(msg.msg_type === 'video') contentHTML = `<video src="${msg.content}" controls class="rounded-lg max-h-64 w-full bg-black"></video>`;
            else if(msg.msg_type === 'voice') contentHTML = `<audio src="${msg.content}" controls class="h-8 w-56"></audio>`;

            const html = `
            <div class="flex ${align} fade-in w-full mb-1" id="msg-${msg.id}">
                <div class="${bg} p-2.5 px-3 shadow-sm msg-bubble">
                    ${!isMe && currentChat.type === 'group' ? `<p class="text-[10px] text-pink-300 mb-1 font-bold opacity-80">کاربر</p>` : ''}
                    ${contentHTML}
                    <div class="flex items-center justify-end gap-1 mt-1 opacity-60 absolute bottom-1 left-2">
                        <span class="text-[9px]">${new Date(msg.timestamp * 1000).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</span>
                        ${tick}
                    </div>
                    <div class="h-3 w-full"></div> <!-- Spacer for absolute time -->
                </div>
            </div>`;
            document.getElementById('messagesList').insertAdjacentHTML('beforeend', html);
        }

        function handleNewMessage(data) {
            let relevant = false;
            if (!currentChat) {
                showToast("پیام جدید دارید");
                return;
            }

            if (currentChat.type === 'group' && data.room_id === currentChat.id) relevant = true;
            else if (currentChat.type === 'pv') {
                const ids = [user.id, currentChat.id].sort();
                const expectedRoom = `${ids[0]}_${ids[1]}`;
                if (data.room_id === expectedRoom) relevant = true;
            }

            if(relevant) {
                renderMessage(data);
                scrollToBottom();
            } else {
                showToast("پیام جدید در گفتگوهای دیگر");
            }
        }

        function updateMessageStatus(id, status) {
            const el = document.querySelector(`#msg-${id} .fa-check`);
            if(el) {
                el.className = `fas fa-check-double text-blue-300 text-[10px]`;
            }
        }

        function scrollToBottom() {
            const el = document.getElementById('messagesList');
            el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
        }

        // --- Sending Logic ---
        function sendText() {
            const input = document.getElementById('msgInput');
            const txt = input.value.trim();
            if(!txt || !currentChat) return;

            const payload = {
                action: 'message',
                target_id: currentChat.id,
                content: txt,
                type: 'text',
                is_group: currentChat.type === 'group'
            };
            ws.send(JSON.stringify(payload));
            input.value = "";
            input.focus();
        }

        async function uploadFile(file) {
            if(!file || !currentChat) return;
            showToast("در حال آپلود...");
            const formData = new FormData();
            formData.append('file', file);
            
            const res = await fetch('/api/upload', {method:'POST', body: formData});
            const data = await res.json();
            
            let type = 'text';
            if(data.type.startsWith('image')) type = 'image';
            else if(data.type.startsWith('video')) type = 'video';
            else if(data.type.startsWith('audio')) type = 'voice';

            const payload = {
                action: 'message',
                target_id: currentChat.id,
                content: data.url,
                type: type,
                is_group: currentChat.type === 'group'
            };
            ws.send(JSON.stringify(payload));
        }

        // --- Group Actions ---
        async function createGroup() {
            const name = document.getElementById('groupNameInp').value;
            if(!name) return;
            const form = new FormData();
            form.append('name', name);
            form.append('user_id', user.id);
            const res = await fetch('/api/create_group', {method:'POST', body:form});
            const data = await res.json();
            alert(`گروه ساخته شد!\nلینک دعوت: ${data.invite_link}`);
            loadChats();
            toggleGroupTools();
        }

        async function joinGroup() {
            const link = document.getElementById('inviteLinkInp').value;
            if(!link) return;
            const form = new FormData();
            form.append('invite_link', link);
            form.append('user_id', user.id);
            const res = await fetch('/api/join_group', {method:'POST', body:form});
            if(res.ok) {
                showToast("عضو شدید!");
                loadChats();
                toggleGroupTools();
            } else showToast("لینک نامعتبر");
        }

        // --- Voice Recording ---
        function startRecording() {
            if(!navigator.mediaDevices) return showToast("مرورگر شما پشتیبانی نمی‌کند");
            const btn = document.getElementById('voiceBtn');
            btn.classList.add('text-red-500', 'scale-125');
            
            navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.start();
                audioChunks = [];
                mediaRecorder.addEventListener("dataavailable", e => audioChunks.push(e.data));
            }).catch(() => showToast("دسترسی میکروفون رد شد"));
        }

        function stopRecording() {
            const btn = document.getElementById('voiceBtn');
            btn.classList.remove('text-red-500', 'scale-125');
            if(mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
                mediaRecorder.addEventListener("stop", () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/mp3' });
                    const file = new File([audioBlob], "voice.mp3", { type: "audio/mp3" });
                    uploadFile(file);
                });
            }
        }
    </script>
</body>
</html>
"""

# --- Database Manager ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, name TEXT, username TEXT UNIQUE, password TEXT, avatar TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS rooms (id TEXT PRIMARY KEY, type TEXT, name TEXT, invite_link TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS room_members (room_id TEXT, user_id TEXT, PRIMARY KEY (room_id, user_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (id TEXT PRIMARY KEY, room_id TEXT, sender_id TEXT, content TEXT, msg_type TEXT, status TEXT, timestamp REAL)''')
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# --- Models ---
class UserLogin(BaseModel):
    username: str
    password: str

class UserRegister(BaseModel):
    name: str
    username: str
    password: str

# --- WebSocket Manager ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(json.dumps(message))

manager = ConnectionManager()

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def get():
    return HTMLResponse(content=html_content)

@app.post("/api/register")
async def register(user: UserRegister):
    conn = get_db_connection()
    try:
        curr = conn.cursor()
        curr.execute("SELECT * FROM users WHERE username=?", (user.username,))
        if curr.fetchone():
            return JSONResponse({"error": "نام کاربری تکراری است"}, status_code=400)
        
        uid = str(uuid.uuid4())
        curr.execute("INSERT INTO users (id, name, username, password, avatar) VALUES (?, ?, ?, ?, ?)",
                     (uid, user.name, user.username, user.password, "default"))
        conn.commit()
        return {"id": uid, "name": user.name, "username": user.username}
    finally:
        conn.close()

@app.post("/api/login")
async def login(user: UserLogin):
    conn = get_db_connection()
    try:
        curr = conn.cursor()
        curr.execute("SELECT * FROM users WHERE username=? AND password=?", (user.username, user.password))
        row = curr.fetchone()
        if row:
            return {"id": row['id'], "name": row['name'], "username": row['username']}
        return JSONResponse({"error": "نام کاربری یا رمز عبور اشتباه است"}, status_code=401)
    finally:
        conn.close()

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    ext = file.filename.split('.')[-1]
    filename = f"{file_id}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
    
    return {"url": f"/static/uploads/{filename}", "type": file.content_type}

@app.post("/api/create_group")
async def create_group(name: str = Form(...), user_id: str = Form(...)):
    conn = get_db_connection()
    room_id = str(uuid.uuid4())
    invite = str(uuid.uuid4())[:8]
    c = conn.cursor()
    c.execute("INSERT INTO rooms (id, type, name, invite_link) VALUES (?, ?, ?, ?)", 
              (room_id, 'group', name, invite))
    c.execute("INSERT INTO room_members (room_id, user_id) VALUES (?, ?)", (room_id, user_id))
    conn.commit()
    conn.close()
    return {"room_id": room_id, "name": name, "invite_link": invite}

@app.post("/api/join_group")
async def join_group(invite_link: str = Form(...), user_id: str = Form(...)):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM rooms WHERE invite_link=?", (invite_link,))
    room = c.fetchone()
    if not room:
        return JSONResponse({"error": "لینک نامعتبر است"}, status_code=404)
    
    # Check if already member
    c.execute("SELECT * FROM room_members WHERE room_id=? AND user_id=?", (room['id'], user_id))
    if not c.fetchone():
        c.execute("INSERT INTO room_members (room_id, user_id) VALUES (?, ?)", (room['id'], user_id))
        conn.commit()
    conn.close()
    return {"room_id": room['id'], "name": room['name']}

@app.get("/api/my_chats/{user_id}")
async def my_chats(user_id: str):
    conn = get_db_connection()
    c = conn.cursor()
    # Get Groups
    c.execute('''SELECT r.id, r.name, r.type FROM rooms r 
                 JOIN room_members rm ON r.id = rm.room_id 
                 WHERE rm.user_id = ?''', (user_id,))
    groups = [{"id": row['id'], "name": row['name'], "type": row['type']} for row in c.fetchall()]
    # Get All Users (PV)
    c.execute("SELECT id, name, username FROM users WHERE id != ?", (user_id,))
    users = [{"id": row['id'], "name": row['name'], "type": "pv"} for row in c.fetchall()]
    conn.close()
    return {"groups": groups, "users": users}

@app.get("/api/messages/{room_id}")
async def get_messages(room_id: str):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM messages WHERE room_id=? ORDER BY timestamp ASC", (room_id,))
    msgs = [dict(row) for row in c.fetchall()]
    conn.close()
    return msgs

# --- WebSocket Logic ---
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            msg_data = json.loads(data)
            action = msg_data.get("action")
            
            if action == "message":
                target_id = msg_data.get("target_id")
                msg_type = msg_data.get("type", "text")
                content = msg_data.get("content")
                is_group = msg_data.get("is_group", False)
                msg_id = str(uuid.uuid4())
                timestamp = time.time()
                
                if is_group:
                    actual_room_id = target_id
                else:
                    ids = sorted([client_id, target_id])
                    actual_room_id = f"{ids[0]}_{ids[1]}"

                conn = get_db_connection()
                c = conn.cursor()
                c.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (msg_id, actual_room_id, client_id, content, msg_type, "sent", timestamp))
                conn.commit()
                conn.close()

                payload = {
                    "action": "new_message",
                    "id": msg_id,
                    "sender_id": client_id,
                    "room_id": actual_room_id,
                    "content": content,
                    "type": msg_type,
                    "timestamp": timestamp,
                    "is_group": is_group
                }

                await manager.send_personal_message(payload, client_id)
                
                if is_group:
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("SELECT user_id FROM room_members WHERE room_id=?", (target_id,))
                    members = c.fetchall()
                    conn.close()
                    for m in members:
                        if m['user_id'] != client_id:
                            await manager.send_personal_message(payload, m['user_id'])
                else:
                    await manager.send_personal_message(payload, target_id)
            
            elif action == "read":
                msg_id = msg_data.get("msg_id")
                sender_of_msg = msg_data.get("sender_id")
                
                conn = get_db_connection()
                conn.execute("UPDATE messages SET status='seen' WHERE id=?", (msg_id,))
                conn.commit()
                conn.close()
                
                await manager.send_personal_message({
                    "action": "status_update",
                    "msg_id": msg_id,
                    "status": "seen"
                }, sender_of_msg)

    except WebSocketDisconnect:
        manager.disconnect(client_id)

# --- START SERVER (Fix for Render) ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)