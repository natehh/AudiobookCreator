async function loadDemoVoices(selectElement) {
    try {
        const response = await fetch('/api/pricing/voices');
        const voiceTiers = await response.json();
        
        selectElement.innerHTML = `
            <option value="">Select a voice</option>
            ${voiceTiers.map(tier => `
                <optgroup label="${tier.tier_name} - $${tier.price_per_char.toFixed(6)}/char">
                    ${tier.voices.map(voice => `
                        <option value="/static/demo_files/${voice.voice_id}.mp3" data-name="${voice.name}" data-country="${voice.country}">
                            ${voice.name} (${voice.country})
                        </option>
                    `).join('')}
                </optgroup>
            `).join('')}
        `;
    } catch (error) {
        console.error('Error loading demo voices:', error);
    }
}

function setupDemoPlayer(containerId) {
    const container = document.getElementById(containerId);
    let currentAudio = null;
    
    container.innerHTML = `
        <div class="demo-section">
            <h2>Try a sample</h2>
            <div class="demo-text">
                <p>It was the best of times, it was the worst of times, it was the age of wisdom, it was the age of foolishness...</p>
            </div>
            <div class="demo-controls">
                <select class="voice-select demo-voice-select">
                    <option value="">Select a voice</option>
                </select>
                <button class="demo-button">▶ Play Sample</button>
            </div>
        </div>
    `;

    const select = container.querySelector('.demo-voice-select');
    const button = container.querySelector('.demo-button');
    
    loadDemoVoices(select);

    button.addEventListener('click', async () => {
        if (!select.value) {
            return;
        }

        if (currentAudio) {
            currentAudio.pause();
            currentAudio = null;
            button.textContent = '▶ Play Sample';
            return;
        }

        button.disabled = true;
        button.textContent = 'Loading...';

        try {
            currentAudio = new Audio(select.value);
            currentAudio.onerror = () => {
                console.error('Error loading audio file:', select.value);
                button.textContent = '▶ Play Sample';
                button.disabled = false;
                currentAudio = null;
            };
            await currentAudio.play();
            button.textContent = '⏸ Pause';
            button.disabled = false;

            currentAudio.onended = () => {
                button.textContent = '▶ Play Sample';
                currentAudio = null;
            };
        } catch (error) {
            console.error('Error playing audio:', error);
            button.textContent = '▶ Play Sample';
            button.disabled = false;
            currentAudio = null;
        }
    });
}

function initializeDemoPlayer() {
    setupDemoPlayer('demoPlayer');
} 