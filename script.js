document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('chat-form');
    const input = document.getElementById('user-input');
    const messagesContainer = document.getElementById('chat-messages');
    const emotionIndicator = document.getElementById('emotion-indicator');

    let currentPersona = 'friend';
    let currentMode = 'typing';

    const personaOptions = document.querySelectorAll('#persona-slider .persona-option');
    personaOptions.forEach(option => {
        option.addEventListener('click', () => {
            personaOptions.forEach(opt => opt.classList.remove('active'));
            option.classList.add('active');
            currentPersona = option.getAttribute('data-persona');
        });
    });

    const modeOptions = document.querySelectorAll('#mode-slider .persona-option');
    const micBtn = document.getElementById('mic-btn');
    const sendBtn = document.getElementById('send-btn');
    const userInput = document.getElementById('user-input');

    modeOptions.forEach(option => {
        option.addEventListener('click', () => {
            modeOptions.forEach(opt => opt.classList.remove('active'));
            option.classList.add('active');
            currentMode = option.getAttribute('data-mode');

            if (currentMode === 'speaking') {
                micBtn.style.display = 'flex';
                sendBtn.style.display = 'none';
                userInput.placeholder = "Press mic to speak...";
                userInput.readOnly = true;
            } else {
                micBtn.style.display = 'none';
                sendBtn.style.display = 'flex';
                userInput.placeholder = "Type a message...";
                userInput.readOnly = false;
            }
        });
    });

    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;
    let recognition;

    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;

        recognition.onresult = (event) => {
            let interimTranscript = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {

                } else {
                    interimTranscript += event.results[i][0].transcript;
                }
            }
            if (interimTranscript) {
                userInput.value = interimTranscript;
                const subText = document.getElementById('subtitles-text');
                const subContainer = document.getElementById('subtitles-container');
                if (subText && subContainer) {
                    subText.innerText = interimTranscript;
                    subContainer.style.display = 'block';
                }
            }
        };

        recognition.onerror = (event) => {
            console.error("Speech recognition error", event.error);
        };
    }

    micBtn.addEventListener('click', async () => {
        if (!isRecording) {
            startRecording();
        } else {
            stopRecording();
        }
    });

    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType });
                await handleVoiceInput(audioBlob);
            };

            mediaRecorder.start();
            isRecording = true;
            micBtn.classList.add('recording');

            if (recognition) {
                userInput.value = '';
                const subContainer = document.getElementById('subtitles-container');
                if (subContainer) subContainer.style.display = 'block';
                recognition.start();
            }
        } catch (err) {
            console.error("Microphone access denied:", err);
            alert("Could not access microphone. Please check permissions.");
        }
    }

    function stopRecording() {
        mediaRecorder.stop();
        isRecording = false;
        micBtn.classList.remove('recording');
        const subContainer = document.getElementById('subtitles-container');
        if (subContainer) subContainer.style.display = 'none';
        if (recognition) {
            recognition.stop();
        }
    }

    async function handleVoiceInput(blob) {
        const formData = new FormData();
        formData.append('audio', blob);

        const typingId = showTypingIndicator();

        try {

            const localTranscription = userInput.value;

            const response = await fetch('/speech-to-text', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();

            removeMessage(typingId);

            const finalTranscription = (data.text && data.text.trim().length > 0) ? data.text : localTranscription;

            if (finalTranscription && finalTranscription.trim().length > 0) {
                appendMessage(finalTranscription, 'user');
                await getChatResponse(finalTranscription);
            } else {
                appendMessage("I couldn't hear you clearly. Could you try again?", 'bot');
            }
        } catch (error) {
            console.error("STT Error:", error);
            removeMessage(typingId);

            const localFallback = userInput.value;
            if (localFallback && localFallback.trim().length > 0) {
                appendMessage(localFallback, 'user');
                await getChatResponse(localFallback);
            } else {
                appendMessage("Error processing voice input.", 'bot');
            }
        }
    }

    async function getChatResponse(message) {
        const typingId = showTypingIndicator();
        try {
            const userId = localStorage.getItem('user_id') || '';
            const prefs = JSON.parse(localStorage.getItem('oasis_user_prefs') || '{}');
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message,
                    user_id: userId,
                    persona: currentPersona,
                    user_preferences: prefs
                })
            });

            const data = await response.json();
            removeMessage(typingId);

            if (data.error) {
                appendMessage("Sorry, an error occurred. Please try again.", 'bot');
            } else {
                appendMessage(data.response, 'bot');

                if (currentMode === 'speaking') {
                    playVoiceResponse(data.response);
                }

                if (data.emotion) {
                    const label = emotionIndicator.querySelector('.emotion-label');
                    label.textContent = `Vibe: ${data.emotion.charAt(0).toUpperCase() + data.emotion.slice(1)}`;
                    emotionIndicator.style.display = 'flex';
                    emotionIndicator.classList.add('active');
                    updateBackgroundVibe(data.emotion);
                }
            }
        } catch (error) {
            console.error('Error:', error);
            removeMessage(typingId);
            appendMessage("Unable to connect to Oasis right now.", 'bot');
        }
    }

    async function playVoiceResponse(text) {
        try {
            const response = await fetch('/text-to-speech', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text })
            });
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            audio.play();
        } catch (error) {
            console.error("TTS Error:", error);
        }
    }

    let vantaEffect = VANTA.NET({
        el: "#vanta-bg",
        mouseControls: true,
        touchControls: true,
        gyroControls: false,
        minHeight: 200.00,
        minWidth: 200.00,
        scale: 1.00,
        scaleMobile: 1.00,
        color: 0x8c7dbd,
        backgroundColor: 0x272242,
        points: 15.00,
        maxDistance: 22.00,
        spacing: 16.00,
        showDots: true
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const message = input.value.trim();
        if (!message) return;

        appendMessage(message, 'user');
        input.value = '';

        await getChatResponse(message);
    });

    function appendMessage(text, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';

        if (sender === 'bot') {
            let formattedText = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            formattedText = formattedText.replace(/\*(.*?)\*/g, '<em>$1</em>');
            formattedText = formattedText.replace(/\n/g, '<br>');
            contentDiv.innerHTML = formattedText;
        } else {
            contentDiv.textContent = text;
        }

        messageDiv.appendChild(contentDiv);
        messagesContainer.appendChild(messageDiv);

        messagesContainer.scrollTo({
            top: messagesContainer.scrollHeight,
            behavior: 'smooth'
        });
    }

    function showTypingIndicator() {
        const id = 'typing-' + Date.now();
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message bot-message';
        messageDiv.id = id;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content typing-indicator';

        for (let i = 0; i < 3; i++) {
            const dot = document.createElement('div');
            dot.className = 'dot';
            contentDiv.appendChild(dot);
        }

        messageDiv.appendChild(contentDiv);
        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;

        return id;
    }

    function removeMessage(id) {
        const el = document.getElementById(id);
        if (el) {
            el.remove();
        }
    }

    function updateBackgroundVibe(emotion) {

        let emotionColor = 0x8c7dbd;

        switch (emotion.toLowerCase()) {
            case 'joy':
                emotionColor = 0xffd700;
                break;
            case 'sadness':
                emotionColor = 0x4169e1;
                break;
            case 'anger':
                emotionColor = 0xff4500;
                break;
            case 'fear':
                emotionColor = 0x9370db;
                break;
            case 'surprise':
                emotionColor = 0x00fa9a;
                break;
            case 'neutral':
                emotionColor = 0x8c7dbd;
                break;
            case 'disgust':
                emotionColor = 0x2e8b57;
                break;
        }

        if (vantaEffect) {
            vantaEffect.setOptions({
                color: emotionColor
            });
        }
    }
});
