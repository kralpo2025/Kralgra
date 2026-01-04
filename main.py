import sqlite3
import json
import os
import uuid
import time
import shutil
from typing import List, Dict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import aiofiles
import uvicorn

app = FastAPI()

# --- Config & Setup ---
DB_NAME = "kralgram.db"
UPLOAD_DIR = "static/uploads"

os.makedirs(UPLOAD_DIR, exist_ok=True)
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
            height: 100dvh;
            overflow: hidden;
            color: white;
            margin: 0; padding: 0;
        }
        @keyframes gradientBG { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
        
        /* Glassmorphism */
        .glass { background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.1); }
        .glass-panel { box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2); }
        .glass-input { background: rgba(0, 0, 0, 0.3); border: 1px solid rgba(255, 255, 255, 0.1); color: white; }
        .glass-input:focus { outline: none; border-color: #4facfe; background: rgba(0, 0, 0, 0.5); }
        
        .msg-bubble { max-width: 85%; word-wrap: break-word; position: relative; }
        .msg-sent { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 16px 16px 0 16px; }
        .msg-received { background: rgba(255, 255, 255, 0.15); border-radius: 16px 16px 16px 0; }
        
        /* Mobile Layout */
        .mobile-screen { position: absolute; top: 0; left: 0; width: 100%; height: 100%; transition: transform 0.3s ease-in-out; background: transparent; }
        .show-chat .mobile-sidebar { transform: translateX(100%); }
        .show-chat .mobile-chat { transform: translateX(0); }
        .mobile-sidebar { z-index: 20; background: rgba(15, 12, 41, 0.95); backdrop-filter: blur(10px); }
        .mobile-chat { transform: translateX(-100%); z-index: 30; background: #1a1a2e; }
        
        @media (min-width: 768px) {
            .mobile-sidebar { position: relative; transform: none !important; width: 30%; background: transparent; }
            .mobile-chat { position: relative; transform: none !important; width: 70%; background: transparent; }
            .back-btn { display: none; }
        }
        
        /* Modal */
        .modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.8); z-index: 50; display: flex; align-items: center; justify-content: center; opacity: 0; pointer-events: none; transition: opacity 0.3s; backdrop-filter: blur(5px); }
        .modal-overlay.open { opacity: 1; pointer-events: auto; }
        .modal-content { transform: scale(0.9); transition: transform 0.3s; max-height: 90vh; overflow-y: auto; }
        .modal-overlay.open .modal-content { transform: scale(1); }

        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 10px; }
        .hidden-page { display: none !important; }
        .fade-in { animation: fadeIn 0.4s ease-in-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
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
            <input type="text" id="l_username" placeholder="نام کاربری" class="w-full p-4 rounded-xl glass-input text-left" dir="ltr">
            <input type="password" id="l_password" placeholder="رمز عبور" class="w-full p-4 rounded-xl glass-input text-left" dir="ltr">
            <button type="submit" class="w-full py-4 rounded-xl bg-gradient-to-r from-blue-600 to-purple-700 font-bold shadow-lg text-white active:scale-95 transition">ورود</button>
        </form>
        <form id="registerForm" class="space-y-4 hidden-page">
            <input type="text" id="r_name" placeholder="نام نمایشی (مثلا: علی)" class="w-full p-4 rounded-xl glass-input">
            <input type="text" id="r_username" placeholder="نام کاربری (انگلیسی)" class="w-full p-4 rounded-xl glass-input text-left" dir="ltr">
            <input type="password" id="r_password" placeholder="رمز عبور" class="w-full p-4 rounded-xl glass-input text-left" dir="ltr">
            <button type="submit" class="w-full py-4 rounded-xl bg-gradient-to-r from-purple-600 to-pink-700 font-bold shadow-lg text-white active:scale-95 transition">ساخت حساب</button>
        </form>
    </div>

    <!-- Main App -->
    <div id="mainApp" class="hidden-page w-full h-full md:h-[90vh] md:w-[95vw] md:max-w-6xl md:glass md:glass-panel md:rounded-3xl flex overflow-hidden relative">
        
        <!-- Sidebar -->
        <div class="mobile-sidebar mobile-screen flex flex-col h-full border-l border-white/5" id="sidebarPanel">
            <div class="p-4 glass border-b border-white/5 flex justify-between items-center z-10">
                <div class="flex items-center gap-3 cursor-pointer" onclick="openProfileModal()">
                    <img id="myAvatarImg" src="" class="w-11 h-11 rounded-full object-cover bg-gray-700 hidden">
                    <div id="myAvatarFallback" class="w-11 h-11 rounded-full bg-gradient-to-br from-yellow-400 to-orange-600 flex items-center justify-center text-lg font-bold shadow-inner">U</div>
                    <div class="flex flex-col">
                        <h3 class="font-bold text-lg leading-tight" id="myName">کاربر</h3>
                        <span class="text-[10px] text-green-400 flex items-center gap-1"><span class="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse"></span> آنلاین</span>
                    </div>
                </div>
                <div class="flex gap-2">
                    <button onclick="openSearchModal()" class="w-10 h-10 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center transition"><i class="fas fa-search"></i></button>
                    <button onclick="toggleGroupTools()" class="w-10 h-10 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center transition"><i class="fas fa-plus"></i></button>
                </div>
            </div>

            <!-- Group Tools -->
            <div id="groupTools" class="p-4 bg-black/40 backdrop-blur-md hidden border-b border-white/10">
                <div class="flex gap-2 mb-3">
                    <input type="text" id="groupNameInp" placeholder="نام گروه جدید" class="flex-1 p-2 rounded-lg glass-input text-sm">
                    <button onclick="createGroup()" class="bg-blue-600 px-3 rounded-lg text-sm">ایجاد</button>
                </div>
                <div class="flex gap-2">
                    <input type="text" id="inviteLinkInp" placeholder="لینک دعوت" class="flex-1 p-2 rounded-lg glass-input text-sm text-left" dir="ltr">
                    <button onclick="joinGroup()" class="bg-green-600 px-3 rounded-lg text-sm">عضویت</button>
                </div>
            </div>

            <div class="flex-1 overflow-y-auto p-2 space-y-1" id="chatList"></div>
        </div>

        <!-- Chat Area -->
        <div class="mobile-chat mobile-screen flex flex-col h-full bg-[#0b0b14]/80 backdrop-blur-sm" id="chatPanel">
            <div id="emptyState" class="absolute inset-0 flex flex-col items-center justify-center text-center p-8 z-0 hidden md:flex">
                <div class="w-24 h-24 bg-white/5 rounded-full flex items-center justify-center mb-4"><i class="fas fa-comments text-4xl text-white/50"></i></div>
                <p class="text-gray-400">یک گفتگو انتخاب کنید</p>
            </div>

            <div class="p-3 glass border-b border-white/5 flex items-center gap-3 z-10 shrink-0 shadow-sm cursor-pointer" onclick="openChatInfo()">
                <button onclick="backToSidebar(); event.stopPropagation();" class="back-btn w-10 h-10 rounded-full active:bg-white/10 flex items-center justify-center text-gray-300"><i class="fas fa-arrow-right"></i></button>
                <div class="w-10 h-10 rounded-full bg-gray-600 flex items-center justify-center font-bold text-sm shadow-lg overflow-hidden">
                     <span id="chatHeaderAvatar">?</span>
                     <img id="chatHeaderImg" class="w-full h-full object-cover hidden">
                </div>
                <div class="flex-1 overflow-hidden">
                    <h3 class="font-bold truncate" id="chatHeaderName">...</h3>
                    <p class="text-xs text-blue-300 truncate" id="chatHeaderInfo">...</p>
                </div>
            </div>

            <div class="flex-1 overflow-y-auto p-4 space-y-3 relative" id="messagesList"></div>

            <div class="p-2 glass shrink-0 z-20">
                <div class="flex items-end gap-2 bg-black/30 p-1.5 rounded-3xl border border-white/5">
                    <button onclick="document.getElementById('fileInput').click()" class="w-10 h-10 rounded-full text-gray-400 hover:text-white flex items-center justify-center transition shrink-0"><i class="fas fa-paperclip text-lg"></i></button>
                    <input type="file" id="fileInput" class="hidden" onchange="uploadFile(this.files[0])">
                    <textarea id="msgInput" rows="1" placeholder="پیام..." class="flex-1 bg-transparent p-2.5 text-white focus:outline-none resize-none overflow-hidden max-h-32 text-sm leading-6" style="min-height: 44px;"></textarea>
                    <button id="voiceBtn" class="w-10 h-10 rounded-full text-gray-400 hover:text-red-400 flex items-center justify-center transition shrink-0" onmousedown="startRecording()" onmouseup="stopRecording()" ontouchstart="startRecording()" ontouchend="stopRecording()"><i class="fas fa-microphone text-lg"></i></button>
                    <button onclick="sendText()" class="w-11 h-11 rounded-full bg-blue-600 text-white flex items-center justify-center shadow-lg active:scale-90 transition shrink-0"><i class="fas fa-paper-plane text-sm translate-x-px translate-y-px"></i></button>
                </div>
            </div>
        </div>
    </div>

    <!-- Profile Modal -->
    <div id="profileModal" class="modal-overlay">
        <div class="modal-content glass glass-panel p-6 rounded-2xl w-80 text-center relative bg-[#1a1a2e]">
            <button onclick="closeModal('profileModal')" class="absolute top-3 right-3 text-gray-400"><i class="fas fa-times"></i></button>
            <div class="relative w-24 h-24 mx-auto mb-4 group">
                <img id="profileModalImg" src="" class="w-full h-full rounded-full object-cover hidden border-2 border-blue-500">
                <div id="profileModalFallback" class="w-full h-full rounded-full bg-gradient-to-br from-yellow-400 to-orange-600 flex items-center justify-center text-3xl font-bold">U</div>
                <button onclick="document.getElementById('avatarInput').click()" class="absolute inset-0 bg-black/50 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition text-white text-sm"><i class="fas fa-camera mr-1"></i> تغییر</button>
            </div>
            <input type="file" id="avatarInput" class="hidden" accept="image/*" onchange="uploadAvatar(this.files[0])">
            <h2 id="profileName" class="text-xl font-bold mb-1">کاربر</h2>
            <p id="profileUsername" class="text-gray-400 text-sm mb-4">@username</p>
            <div class="bg-white/5 p-3 rounded-xl mb-2 text-left">
                <p class="text-xs text-gray-400 mb-1">لینک پروفایل شما:</p>
                <div class="flex items-center gap-2 bg-black/20 p-2 rounded border border-white/5 overflow-hidden">
                    <span id="myProfileLink" class="text-xs truncate text-blue-300 flex-1 font-mono">...</span>
                    <button onclick="copyToClipboard('myProfileLink')" class="text-gray-400 hover:text-white"><i class="fas fa-copy"></i></button>
                </div>
            </div>
        </div>
    </div>

    <!-- Search Modal -->
    <div id="searchModal" class="modal-overlay">
        <div class="modal-content glass glass-panel p-6 rounded-2xl w-80 bg-[#1a1a2e]">
            <button onclick="closeModal('searchModal')" class="absolute top-3 right-3 text-gray-400"><i class="fas fa-times"></i></button>
            <h3 class="font-bold mb-4">جستجوی کاربر</h3>
            <div class="flex gap-2">
                <input type="text" id="searchInput" placeholder="نام کاربری (بدون @)" class="flex-1 p-3 rounded-xl glass-input text-left" dir="ltr">
                <button onclick="searchUser()" class="bg-blue-600 px-4 rounded-xl"><i class="fas fa-search"></i></button>
            </div>
        </div>
    </div>

    <!-- Chat Info Modal -->
    <div id="chatInfoModal" class="modal-overlay">
        <div class="modal-content glass glass-panel p-6 rounded-2xl w-80 bg-[#1a1a2e] text-center">
            <button onclick="closeModal('chatInfoModal')" class="absolute top-3 right-3 text-gray-400"><i class="fas fa-times"></i></button>
            <div id="infoAvatar" class="w-20 h-20 rounded-full bg-gray-600 mx-auto mb-3 flex items-center justify-center font-bold text-2xl">?</div>
            <h2 id="infoName" class="text-xl font-bold mb-4">نام</h2>
            
            <div id="groupLinkSection" class="hidden text-left bg-white/5 p-3 rounded-xl">
                <p class="text-xs text-gray-400 mb-1">لینک دعوت گروه:</p>
                <div class="flex items-center gap-2 bg-black/20 p-2 rounded border border-white/5">
                    <span id="groupInviteLink" class="text-xs truncate text-green-300 flex-1 font-mono"></span>
                    <button onclick="copyToClipboard('groupInviteLink')" class="text-gray-400 hover:text-white"><i class="fas fa-copy"></i></button>
                </div>
            </div>
        </div>
    </div>

    <div id="toast" class="fixed top-6 left-1/2 transform -translate-x-1/2 glass px-5 py-3 rounded-2xl shadow-2xl transition-all duration-300 opacity-0 pointer-events-none z-50 flex items-center gap-3"><span id="toastMsg" class="font-bold text-sm"></span></div>

    <script>
        // --- State ---
        let user = JSON.parse(localStorage.getItem('kral_user')) || null;
        let ws = null;
        let currentChat = null;
        let mediaRecorder = null;
        let audioChunks = [];

        // --- Init ---
        if(user) initApp();
        else document.getElementById('authPage').style.display = 'flex';

        // Check for deep link (e.g., /#@username)
        window.onload = () => {
            const hash = window.location.hash;
            if(hash && hash.startsWith('#@') && user) {
                const targetUser = hash.substring(2);
                document.getElementById('searchInput').value = targetUser;
                searchUser(); // Auto open chat
            }
        };

        // --- Modals ---
        function openProfileModal() {
            document.getElementById('profileModal').classList.add('open');
            document.getElementById('profileName').innerText = user.name;
            document.getElementById('profileUsername').innerText = '@' + user.username;
            const link = `${window.location.protocol}//${window.location.host}/#@${user.username}`;
            document.getElementById('myProfileLink').innerText = link;
            
            if(user.avatar && user.avatar !== 'default') {
                const img = document.getElementById('profileModalImg');
                img.src = user.avatar;
                img.classList.remove('hidden');
                document.getElementById('profileModalFallback').classList.add('hidden');
            }
        }
        function openSearchModal() { document.getElementById('searchModal').classList.add('open'); }
        
        async function openChatInfo() {
            if(!currentChat) return;
            document.getElementById('chatInfoModal').classList.add('open');
            document.getElementById('infoName').innerText = currentChat.name;
            document.getElementById('infoAvatar').innerText = currentChat.name[0];
            
            const groupSec = document.getElementById('groupLinkSection');
            if(currentChat.type === 'group') {
                groupSec.classList.remove('hidden');
                // Fetch info
                const res = await fetch(`/api/group_info/${currentChat.id}`);
                const data = await res.json();
                document.getElementById('groupInviteLink').innerText = data.invite_link;
            } else {
                groupSec.classList.add('hidden');
            }
        }

        function closeModal(id) { document.getElementById(id).classList.remove('open'); }
        
        function copyToClipboard(elemId) {
            const txt = document.getElementById(elemId).innerText;
            navigator.clipboard.writeText(txt).then(() => showToast("کپی شد!"));
        }

        // --- Auth & Main ---
        document.getElementById('loginForm').onsubmit = async (e) => handleAuth(e, '/api/login');
        document.getElementById('registerForm').onsubmit = async (e) => handleAuth(e, '/api/register');

        async function handleAuth(e, url) {
            e.preventDefault();
            const inputs = e.target.querySelectorAll('input');
            const body = {};
            inputs.forEach(i => body[i.id.split('_')[1]] = i.value);
            
            try {
                const res = await fetch(url, { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body) });
                const data = await res.json();
                if(res.ok) {
                    localStorage.setItem('kral_user', JSON.stringify(data));
                    user = data;
                    initApp();
                } else showToast(data.error);
            } catch { showToast("خطا در ارتباط"); }
        }

        function toggleAuth(type) {
            document.getElementById(type === 'login' ? 'loginForm' : 'registerForm').classList.remove('hidden-page');
            document.getElementById(type === 'login' ? 'registerForm' : 'loginForm').classList.add('hidden-page');
            // Update tabs visually...
        }

        function initApp() {
            document.getElementById('authPage').classList.add('hidden-page');
            document.getElementById('mainApp').classList.remove('hidden-page');
            document.getElementById('mainApp').classList.add('fade-in');
            
            document.getElementById('myName').innerText = user.name;
            if(user.avatar && user.avatar !== 'default') {
                document.getElementById('myAvatarImg').src = user.avatar;
                document.getElementById('myAvatarImg').classList.remove('hidden');
                document.getElementById('myAvatarFallback').classList.add('hidden');
            }

            connectWS();
            loadChats();
        }

        // --- WebSocket & Real-time ---
        function connectWS() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws/${user.id}`);
            ws.onmessage = (e) => {
                const data = JSON.parse(e.data);
                if (data.action === "new_message") handleNewMessage(data);
                else if (data.action === "status_update") updateMessageStatus(data.msg_id);
            };
            ws.onclose = () => setTimeout(connectWS, 3000);
        }

        function handleNewMessage(data) {
            // Logic to determine if message belongs to current chat
            let relevant = false;
            
            if (currentChat) {
                if (currentChat.type === 'group' && data.room_id === currentChat.id) relevant = true;
                else if (currentChat.type === 'pv') {
                    // Reconstruct room ID for PV
                    const ids = [user.id, currentChat.id].sort();
                    const expected = `${ids[0]}_${ids[1]}`;
                    if(data.room_id === expected) relevant = true;
                }
            }

            if(relevant) {
                renderMessage(data);
                scrollToBottom();
            } else {
                if(data.sender_id !== user.id) showToast("پیام جدید!");
                loadChats(); // Refresh list to show new conversation top
            }
        }

        async function loadChats() {
            const res = await fetch(`/api/my_chats/${user.id}`);
            const data = await res.json();
            const list = document.getElementById('chatList');
            list.innerHTML = "";
            [...data.groups, ...data.users].forEach(c => {
                list.innerHTML += `
                <div onclick="openChat('${c.id}', '${c.name}', '${c.type}', '${c.avatar||''}')" class="p-3 rounded-2xl hover:bg-white/10 cursor-pointer flex items-center gap-3">
                    <div class="w-12 h-12 rounded-full ${c.type==='group'?'bg-indigo-600':'bg-pink-600'} flex items-center justify-center shadow-lg overflow-hidden">
                        ${c.avatar && c.avatar!=='default' ? `<img src="${c.avatar}" class="w-full h-full object-cover">` : `<i class="fas fa-${c.type==='group'?'users':'user'}"></i>`}
                    </div>
                    <div class="flex-1 min-w-0">
                        <h4 class="font-bold text-sm truncate">${c.name}</h4>
                        <p class="text-xs text-gray-400 opacity-70">${c.type==='group'?'گروه':'کاربر'}</p>
                    </div>
                </div>`;
            });
        }

        async function openChat(id, name, type, avatar) {
            currentChat = {id, name, type};
            document.getElementById('mainApp').classList.add('show-chat');
            
            document.getElementById('chatHeaderName').innerText = name;
            document.getElementById('chatHeaderInfo').innerText = type === 'group' ? 'گروه' : 'آنلاین';
            
            const headImg = document.getElementById('chatHeaderImg');
            const headTxt = document.getElementById('chatHeaderAvatar');
            
            if(avatar && avatar !== 'default' && avatar !== 'undefined') {
                headImg.src = avatar;
                headImg.classList.remove('hidden');
                headTxt.classList.add('hidden');
            } else {
                headImg.classList.add('hidden');
                headTxt.classList.remove('hidden');
                headTxt.innerText = name[0];
            }

            // Load messages
            let loadId = id;
            if (type === 'pv') {
                const ids = [user.id, id].sort();
                loadId = `${ids[0]}_${ids[1]}`;
            }

            const list = document.getElementById('messagesList');
            list.innerHTML = '';
            
            const res = await fetch(`/api/messages/${loadId}`);
            const msgs = await res.json();
            msgs.forEach(m => renderMessage(m));
            scrollToBottom();
        }

        function renderMessage(msg) {
            const isMe = msg.sender_id === user.id;
            const list = document.getElementById('messagesList');
            
            // Check for duplicate (optimistic vs real)
            if(document.getElementById(`msg-${msg.id}`)) return;

            let contentHTML = '';
            if(msg.msg_type === 'text') contentHTML = `<p class="leading-relaxed text-sm">${msg.content}</p>`;
            else if(msg.msg_type === 'image') contentHTML = `<img src="${msg.content}" class="rounded-lg max-h-64 object-cover cursor-pointer" onclick="window.open(this.src)" onload="scrollToBottom()">`;
            else if(msg.msg_type === 'voice') contentHTML = `<audio src="${msg.content}" controls class="h-8 w-56"></audio>`;
            else if(msg.msg_type === 'video') contentHTML = `<video src="${msg.content}" controls class="max-h-64 w-full bg-black rounded-lg"></video>`;

            const html = `
            <div class="flex ${isMe?'justify-end':'justify-start'} fade-in w-full mb-1" id="msg-${msg.id}">
                <div class="${isMe?'msg-sent':'msg-received'} p-2.5 px-3 shadow-sm msg-bubble">
                    ${contentHTML}
                    <div class="flex items-center justify-end gap-1 mt-1 opacity-60 absolute bottom-1 left-2">
                        <span class="text-[9px]">${new Date(msg.timestamp * 1000).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</span>
                        ${isMe ? `<i class="fas ${msg.status==='seen'?'fa-check-double text-blue-300':'fa-check text-gray-300'} text-[10px]"></i>` : ''}
                    </div>
                    <div class="h-4 w-full"></div>
                </div>
            </div>`;
            list.insertAdjacentHTML('beforeend', html);
        }

        // --- Actions ---
        function sendText() {
            const input = document.getElementById('msgInput');
            const txt = input.value.trim();
            if(!txt || !currentChat) return;
            
            ws.send(JSON.stringify({
                action: 'message',
                target_id: currentChat.id,
                content: txt,
                type: 'text',
                is_group: currentChat.type === 'group'
            }));
            input.value = "";
        }

        async function uploadFile(file) {
            if(!file || !currentChat) return;
            showToast("در حال ارسال...");
            const form = new FormData();
            form.append('file', file);
            const res = await fetch('/api/upload', {method:'POST', body:form});
            const data = await res.json();
            
            let type = 'text';
            if(data.type.startsWith('image')) type = 'image';
            else if(data.type.startsWith('audio')) type = 'voice';
            else if(data.type.startsWith('video')) type = 'video';
            
            ws.send(JSON.stringify({
                action: 'message',
                target_id: currentChat.id,
                content: data.url,
                type: type,
                is_group: currentChat.type === 'group'
            }));
        }

        async function uploadAvatar(file) {
            if(!file) return;
            const form = new FormData();
            form.append('file', file);
            form.append('user_id', user.id);
            const res = await fetch('/api/update_avatar', {method:'POST', body:form});
            const data = await res.json();
            
            user.avatar = data.url;
            localStorage.setItem('kral_user', JSON.stringify(user));
            document.getElementById('profileModalImg').src = data.url;
            document.getElementById('profileModalImg').classList.remove('hidden');
            document.getElementById('profileModalFallback').classList.add('hidden');
            document.getElementById('myAvatarImg').src = data.url;
            document.getElementById('myAvatarImg').classList.remove('hidden');
            document.getElementById('myAvatarFallback').classList.add('hidden');
            showToast("پروفایل آپدیت شد");
        }

        async function searchUser() {
            const query = document.getElementById('searchInput').value.trim();
            if(!query) return;
            
            const res = await fetch(`/api/search_user?query=${query}`);
            const data = await res.json();
            
            if(data.error) showToast("کاربر یافت نشد");
            else {
                closeModal('searchModal');
                // Open Chat directly
                openChat(data.id, data.name, 'pv', data.avatar);
            }
        }

        async function createGroup() {
            const name = document.getElementById('groupNameInp').value;
            if(!name) return;
            const form = new FormData();
            form.append('name', name); form.append('user_id', user.id);
            await fetch('/api/create_group', {method:'POST', body:form});
            loadChats();
            document.getElementById('groupNameInp').value = "";
            showToast("گروه ساخته شد");
        }

        async function joinGroup() {
            const link = document.getElementById('inviteLinkInp').value;
            const form = new FormData();
            form.append('invite_link', link); form.append('user_id', user.id);
            const res = await fetch('/api/join_group', {method:'POST', body:form});
            if(res.ok) { loadChats(); showToast("عضو شدید!"); }
            else showToast("لینک نامعتبر");
        }

        // Voice
        function startRecording() {
            navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
                mediaRecorder = new MediaRecorder(stream);
                mediaRecorder.start();
                audioChunks = [];
                mediaRecorder.addEventListener("dataavailable", e => audioChunks.push(e.data));
                document.getElementById('voiceBtn').classList.add('text-red-500', 'scale-125');
            });
        }
        function stopRecording() {
            if(mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
                mediaRecorder.addEventListener("stop", () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/mp3' });
                    uploadFile(new File([audioBlob], "voice.mp3", { type: "audio/mp3" }));
                    document.getElementById('voiceBtn').classList.remove('text-red-500', 'scale-125');
                });
            }
        }
        
        function scrollToBottom() {
            const el = document.getElementById('messagesList');
            el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
        }
        function updateMessageStatus(id) {
             const el = document.querySelector(`#msg-${id} .fa-check`);
             if(el) el.className = "fas fa-check-double text-blue-300 text-[10px]";
        }
        function backToSidebar() { document.getElementById('mainApp').classList.remove('show-chat'); currentChat = null; }
        function showToast(msg) {
            const t = document.getElementById('toast');
            document.getElementById('toastMsg').innerText = msg;
            t.classList.remove('opacity-0', '-translate-y-4');
            setTimeout(() => t.classList.add('opacity-0', '-translate-y-4'), 3000);
        }
    </script>
</body>
</html>
"""

# --- Backend ---

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

# --- Cleanup Task (24 Hours) ---
def cleanup_storage():
    now = time.time()
    # Delete files older than 24 hours (86400 seconds)
    limit = now - 86400 
    for filename in os.listdir(UPLOAD_DIR):
        file_path = os.path.join(UPLOAD_DIR, filename)
        if os.path.getmtime(file_path) < limit:
            try:
                os.remove(file_path)
                print(f"Deleted old file: {filename}")
            except Exception as e:
                print(f"Error deleting {filename}: {e}")

# --- Models ---
class UserLogin(BaseModel):
    username: str
    password: str

class UserRegister(BaseModel):
    name: str
    username: str
    password: str

# --- WebSocket ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
    def disconnect(self, user_id: str):
        if user_id in self.active_connections: del self.active_connections[user_id]
    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(json.dumps(message))

manager = ConnectionManager()

# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def get(): return HTMLResponse(content=html_content)

@app.post("/api/register")
async def register(user: UserRegister):
    conn = get_db_connection()
    try:
        curr = conn.cursor()
        curr.execute("SELECT * FROM users WHERE username=?", (user.username,))
        if curr.fetchone(): return JSONResponse({"error": "نام کاربری تکراری"}, 400)
        uid = str(uuid.uuid4())
        curr.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?)", (uid, user.name, user.username, user.password, "default"))
        conn.commit()
        return {"id": uid, "name": user.name, "username": user.username, "avatar": "default"}
    finally: conn.close()

@app.post("/api/login")
async def login(user: UserLogin):
    conn = get_db_connection()
    curr = conn.cursor()
    curr.execute("SELECT * FROM users WHERE username=? AND password=?", (user.username, user.password))
    row = curr.fetchone()
    conn.close()
    if row: return {"id": row['id'], "name": row['name'], "username": row['username'], "avatar": row['avatar']}
    return JSONResponse({"error": "اطلاعات اشتباه است"}, 401)

@app.post("/api/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    # Trigger cleanup on upload to save space
    background_tasks.add_task(cleanup_storage)
    
    file_id = str(uuid.uuid4())
    ext = file.filename.split('.')[-1]
    filename = f"{file_id}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    async with aiofiles.open(file_path, 'wb') as out_file:
        content = await file.read()
        await out_file.write(content)
    return {"url": f"/static/uploads/{filename}", "type": file.content_type}

@app.post("/api/update_avatar")
async def update_avatar(file: UploadFile = File(...), user_id: str = Form(...)):
    file_id = str(uuid.uuid4())
    filename = f"avatar_{file_id}.jpg"
    file_path = os.path.join(UPLOAD_DIR, filename)
    async with aiofiles.open(file_path, 'wb') as out_file:
        await out_file.write(await file.read())
    
    url = f"/static/uploads/{filename}"
    conn = get_db_connection()
    conn.execute("UPDATE users SET avatar=? WHERE id=?", (url, user_id))
    conn.commit()
    conn.close()
    return {"url": url}

@app.get("/api/search_user")
async def search_user(query: str):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, name, avatar FROM users WHERE username=?", (query,))
    row = c.fetchone()
    conn.close()
    if row: return {"id": row['id'], "name": row['name'], "avatar": row['avatar']}
    return {"error": "Not found"}

@app.post("/api/create_group")
async def create_group(name: str = Form(...), user_id: str = Form(...)):
    conn = get_db_connection()
    room_id = str(uuid.uuid4())
    invite = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO rooms VALUES (?, ?, ?, ?)", (room_id, 'group', name, invite))
    conn.execute("INSERT INTO room_members VALUES (?, ?)", (room_id, user_id))
    conn.commit()
    conn.close()
    return {"room_id": room_id, "invite_link": invite}

@app.post("/api/join_group")
async def join_group(invite_link: str = Form(...), user_id: str = Form(...)):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM rooms WHERE invite_link=?", (invite_link,))
    room = c.fetchone()
    if not room: return JSONResponse({"error": "لینک نامعتبر"}, 404)
    c.execute("SELECT * FROM room_members WHERE room_id=? AND user_id=?", (room['id'], user_id))
    if not c.fetchone():
        c.execute("INSERT INTO room_members VALUES (?, ?)", (room['id'], user_id))
        conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/api/group_info/{room_id}")
async def group_info(room_id: str):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT invite_link FROM rooms WHERE id=?", (room_id,))
    row = c.fetchone()
    conn.close()
    return {"invite_link": row['invite_link'] if row else ""}

@app.get("/api/my_chats/{user_id}")
async def my_chats(user_id: str):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''SELECT r.id, r.name, r.type, '' as avatar FROM rooms r 
                 JOIN room_members rm ON r.id = rm.room_id WHERE rm.user_id = ?''', (user_id,))
    groups = [dict(row) for row in c.fetchall()]
    
    # Simple logic for PV: Find users I have chatted with
    # Complex query to find unique PV partners from messages
    c.execute('''
        SELECT DISTINCT u.id, u.name, u.avatar 
        FROM users u
        WHERE u.id IN (
            SELECT CASE WHEN sender_id = ? THEN replace(room_id, ? || '_', '') 
                        ELSE sender_id END
            FROM messages 
            WHERE room_id LIKE ? OR room_id LIKE ?
        )
    ''', (user_id, user_id, f"%{user_id}%", f"%{user_id}%"))
    
    # Fallback: Just return all users excluding self (for easy demo)
    # In production, use the commented logic above
    c.execute("SELECT id, name, avatar FROM users WHERE id != ?", (user_id,))
    users = [{"id": row['id'], "name": row['name'], "type": "pv", "avatar": row['avatar']} for row in c.fetchall()]
    
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
                
                if is_group: actual_room_id = target_id
                else:
                    ids = sorted([client_id, target_id])
                    actual_room_id = f"{ids[0]}_{ids[1]}"

                conn = get_db_connection()
                conn.execute("INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (msg_id, actual_room_id, client_id, content, msg_type, "sent", timestamp))
                conn.commit()
                conn.close()

                payload = {"action": "new_message", "id": msg_id, "sender_id": client_id, "room_id": actual_room_id, "content": content, "type": msg_type, "timestamp": timestamp, "status": "sent"}
                
                # Send to sender (immediate feedback)
                await manager.send_personal_message(payload, client_id)
                
                if is_group:
                    conn = get_db_connection()
                    members = conn.execute("SELECT user_id FROM room_members WHERE room_id=?", (target_id,)).fetchall()
                    conn.close()
                    for m in members:
                        if m[0] != client_id: await manager.send_personal_message(payload, m[0])
                else:
                    await manager.send_personal_message(payload, target_id)
            
            elif action == "read":
                msg_id = msg_data.get("msg_id")
                sender = msg_data.get("sender_id")
                conn = get_db_connection()
                conn.execute("UPDATE messages SET status='seen' WHERE id=?", (msg_id,))
                conn.commit()
                conn.close()
                await manager.send_personal_message({"action": "status_update", "msg_id": msg_id, "status": "seen"}, sender)

    except WebSocketDisconnect: manager.disconnect(client_id)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)