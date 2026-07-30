/**
 * Match Simulator — JavaScript
 * ==============================
 * Client-side wizard state machine for the Match Simulator feature.
 * Manages: difficulty/formation selection, pitch rendering, player
 * picker modal, bench assignment, API calls (validate + simulate),
 * match animation, and result screen rendering.
 */

document.addEventListener('DOMContentLoaded', () => {

    // ============================================================
    // DATA (injected from template)
    // ============================================================
    const allPlayers = window.MSIM_PLAYERS || [];
    const formations = window.MSIM_FORMATIONS || {};

    // ============================================================
    // STATE
    // ============================================================
    let selectedDifficulty = 'normal';
    let selectedFormation = '4-3-3';
    let startingXI = {};       // { slotIndex: playerObj }
    let bench = {};            // { benchIndex: playerObj }
    let pickerTarget = null;   // { type: 'xi'|'bench', index: number, position: string, category: string }

    // Set of player IDs already selected (Starting XI + bench)
    function getUsedPlayerIds() {
        const ids = new Set();
        Object.values(startingXI).forEach(p => ids.add(p.id));
        Object.values(bench).forEach(p => ids.add(p.id));
        return ids;
    }

    // Position category mapping (mirrors backend)
    const POSITION_CATEGORIES = {
        'GK': 'GK', 'CB': 'DEF', 'LB': 'DEF', 'RB': 'DEF',
        'CDM': 'MID', 'CM': 'MID', 'CAM': 'MID',
        'LW': 'ATT', 'RW': 'ATT', 'ST': 'ATT',
    };
    const CATEGORY_POSITIONS = {
        'GK': ['GK'],
        'DEF': ['CB', 'LB', 'RB'],
        'MID': ['CDM', 'CM', 'CAM'],
        'ATT': ['LW', 'RW', 'ST'],
    };

    function getCategory(pos) {
        return POSITION_CATEGORIES[pos] || 'MID';
    }

    // ============================================================
    // DOM ELEMENTS
    // ============================================================
    const stepSetup = document.getElementById('step-setup');
    const stepSquad = document.getElementById('step-squad');
    const stepAnimation = document.getElementById('step-animation');
    const stepResult = document.getElementById('step-result');

    const difficultyCards = document.querySelectorAll('.difficulty-card');
    const formationBtns = document.getElementById('formation-buttons');
    const btnStartBuilding = document.getElementById('btn-start-building');
    const btnBackSetup = document.getElementById('btn-back-setup');
    const btnSimulate = document.getElementById('btn-simulate');
    const btnPlayAgain = document.getElementById('btn-play-again');

    const formationLabel = document.getElementById('formation-label');
    const squadCounter = document.getElementById('squad-counter');
    const pitchSlots = document.getElementById('pitch-slots');
    const validationErrors = document.getElementById('validation-errors');
    const validationErrorList = document.getElementById('validation-error-list');

    // Picker modal
    const pickerModal = document.getElementById('picker-modal');
    const pickerOverlay = document.getElementById('picker-overlay');
    const pickerContent = document.getElementById('picker-content');
    const pickerClose = document.getElementById('picker-close');
    const pickerSearch = document.getElementById('picker-search');
    const pickerFilterNat = document.getElementById('picker-filter-nationality');
    const pickerFilterPos = document.getElementById('picker-filter-position');
    const pickerGrid = document.getElementById('picker-grid');
    const pickerSlotLabel = document.getElementById('picker-slot-label');

    // Animation
    const animStage = document.getElementById('anim-stage');

    // Flag helper
    function flagImgHtml(nationality, size = 16) {
        const flags = window.COUNTRY_FLAGS || {};
        const code = flags[nationality];
        if (!code) return '';
        const h = Math.round(size * 0.75);
        return `<img src="https://flagcdn.com/${code}.svg" alt="" width="${size}" height="${h}" style="display:inline-block;vertical-align:middle;border-radius:2px;" loading="lazy">`;
    }


    // ============================================================
    // 1. DIFFICULTY SELECTION
    // ============================================================
    difficultyCards.forEach(card => {
        card.addEventListener('click', () => {
            selectedDifficulty = card.dataset.difficulty;
            difficultyCards.forEach(c => {
                c.classList.remove('ring-2', 'ring-gold-500/30', 'border-gold-500/40', 'dark:border-gold-500/30', 'bg-gold-50/50', 'dark:bg-gold-500/5');
                c.classList.add('border-gray-200/50', 'dark:border-navy-800/50', 'bg-white', 'dark:bg-navy-900');
            });
            card.classList.remove('border-gray-200/50', 'dark:border-navy-800/50', 'bg-white', 'dark:bg-navy-900');
            card.classList.add('ring-2', 'ring-gold-500/30', 'border-gold-500/40', 'dark:border-gold-500/30', 'bg-gold-50/50', 'dark:bg-gold-500/5');
        });
    });


    // ============================================================
    // 2. FORMATION SELECTION
    // ============================================================
    function renderFormationButtons() {
        const names = Object.keys(formations);
        formationBtns.innerHTML = names.map(name => `
            <button data-formation="${name}"
                class="formation-btn px-4 sm:px-5 py-2 sm:py-2.5 rounded-xl text-xs sm:text-sm font-bold uppercase tracking-wider transition-all duration-300 cursor-pointer
                ${name === selectedFormation
                    ? 'bg-gold-500 text-navy-950 shadow-lg shadow-gold-500/20'
                    : 'bg-white dark:bg-navy-900 text-navy-600 dark:text-gray-300 border border-gray-200 dark:border-navy-800 hover:border-gold-500/30'
                }">${name}</button>
        `).join('');

        formationBtns.querySelectorAll('.formation-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const newFormation = btn.dataset.formation;
                if (newFormation !== selectedFormation) {
                    // Unassign players in slots that may no longer exist
                    const newSlots = formations[newFormation];
                    const newSlotCount = newSlots ? newSlots.length : 11;
                    const toRemove = [];
                    for (const idx in startingXI) {
                        if (parseInt(idx) >= newSlotCount) {
                            toRemove.push(parseInt(idx));
                        }
                    }
                    toRemove.forEach(idx => delete startingXI[idx]);

                    selectedFormation = newFormation;
                    renderFormationButtons();
                    renderPitch();
                    updateSquadCounter();
                }
            });
        });
    }
    renderFormationButtons();


    // ============================================================
    // 3. PITCH RENDERING
    // ============================================================
    function renderPitch() {
        const slots = formations[selectedFormation];
        if (!slots) return;

        // Group slots by row
        const rows = {};
        slots.forEach((slot, idx) => {
            const row = slot.formation_row;
            if (!rows[row]) rows[row] = [];
            rows[row].push({ ...slot, slotIndex: idx });
        });

        // Sort row keys ascending (row 1 = top)
        const sortedRows = Object.keys(rows).sort((a, b) => a - b);

        pitchSlots.innerHTML = sortedRows.map(rowKey => {
            const rowSlots = rows[rowKey].sort((a, b) => a.formation_order - b.formation_order);
            const gapClass = rowSlots.length <= 2 ? 'gap-4 sm:gap-8 lg:gap-12'
                : rowSlots.length <= 3 ? 'gap-3 sm:gap-6 lg:gap-10'
                : rowSlots.length === 4 ? 'gap-2.5 sm:gap-5 lg:gap-8'
                : 'gap-2 sm:gap-4 lg:gap-6';

            return `<div class="flex justify-center ${gapClass}">
                ${rowSlots.map(slot => renderSlot(slot)).join('')}
            </div>`;
        }).join('');
    }

    function renderSlot(slot) {
        const player = startingXI[slot.slotIndex];
        const widthClass = slot.position === 'GK' ? 'w-[72px] sm:w-[95px] lg:w-[108px]' : 'w-[68px] sm:w-[88px] lg:w-[100px]';

        if (player) {
            return `
            <div class="match-sim-slot filled group ${widthClass}" data-slot="${slot.slotIndex}">
                <div class="relative overflow-hidden rounded-xl bg-gray-100 dark:bg-navy-900 border border-white/15 hover:border-gold-500/40 transition-all duration-300 hover:shadow-xl hover:shadow-gold-500/10 cursor-pointer"
                     onclick="window.MSim.onSlotClick(${slot.slotIndex}, '${slot.position}')">
                    <div class="aspect-[3/4] player-card-img">
                        <img src="${player.frame_image_url}" alt="" class="frame-layer"
                             onerror="this.src=window.DEFAULT_FRAME_IMAGE_URL">
                        <img src="${player.player_image_url}" alt="${player.name}" class="player-layer"
                             onerror="this.src=window.DEFAULT_PLAYER_IMAGE_URL" loading="lazy">
                    </div>
                    <div class="p-1.5 sm:p-2 bg-navy-950/60 backdrop-blur-sm">
                        <h3 class="font-bold text-white text-[10px] sm:text-xs truncate">${player.name}</h3>
                        <div class="flex items-center justify-between mt-0.5">
                            <span class="inline-block px-1.5 py-0.5 rounded-full text-[9px] font-semibold bg-white/10 text-white/80">${slot.position}</span>
                            <span class="text-[9px] font-bold text-gold-400">${player.overall}</span>
                        </div>
                    </div>
                </div>
                <button class="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-accent-500 hover:bg-accent-600 text-white flex items-center justify-center text-[10px] font-bold z-30 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                        onclick="event.stopPropagation(); window.MSim.removeXIPlayer(${slot.slotIndex})">✕</button>
            </div>`;
        } else {
            const isGK = slot.position === 'GK';
            return `
            <div class="match-sim-slot empty ${widthClass}" data-slot="${slot.slotIndex}"
                 onclick="window.MSim.onSlotClick(${slot.slotIndex}, '${slot.position}')">
                <div class="match-sim-slot-empty cursor-pointer ${isGK ? 'border-gold-500/25' : ''}">
                    <div class="aspect-[3/4] flex flex-col items-center justify-center">
                        <span class="text-xs sm:text-sm font-bold text-white/40">${slot.position}</span>
                        <span class="text-[9px] text-white/25 mt-1">+</span>
                    </div>
                </div>
            </div>`;
        }
    }

    renderPitch();


    // ============================================================
    // 4. BENCH RENDERING
    // ============================================================
    function renderBench() {
        const benchSlotEls = document.querySelectorAll('.match-sim-bench-slot');
        benchSlotEls.forEach(el => {
            const idx = parseInt(el.dataset.benchIndex);
            const cat = el.dataset.benchCategory;
            const player = bench[idx];

            if (player) {
                el.innerHTML = `
                <div class="relative group">
                    <div class="relative overflow-hidden rounded-xl bg-gray-100 dark:bg-navy-900 border border-gray-200/50 dark:border-navy-800/50 hover:border-gold-500/30 transition-all duration-300 cursor-pointer"
                         onclick="window.MSim.openBenchPicker(${idx}, '${cat}')">
                        <div class="aspect-[3/4] player-card-img">
                            <img src="${player.frame_image_url}" alt="" class="frame-layer"
                                 onerror="this.src=window.DEFAULT_FRAME_IMAGE_URL">
                            <img src="${player.player_image_url}" alt="${player.name}" class="player-layer"
                                 onerror="this.src=window.DEFAULT_PLAYER_IMAGE_URL" loading="lazy">
                        </div>
                        <div class="p-1.5 sm:p-2">
                            <h3 class="font-bold text-navy-900 dark:text-white text-[10px] sm:text-xs truncate">${player.name}</h3>
                            <div class="flex items-center justify-between mt-0.5">
                                <span class="inline-block px-1.5 py-0.5 rounded-full text-[9px] font-semibold bg-navy-100 dark:bg-navy-800 text-navy-700 dark:text-navy-200">${player.primary_position}</span>
                                <span class="text-[9px] font-bold text-gold-500">${player.overall}</span>
                            </div>
                        </div>
                    </div>
                    <button class="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-accent-500 hover:bg-accent-600 text-white flex items-center justify-center text-[10px] font-bold z-30 opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                            onclick="event.stopPropagation(); window.MSim.removeBenchPlayer(${idx})">✕</button>
                </div>`;
            } else {
                el.innerHTML = `
                <div class="match-sim-bench-empty cursor-pointer" onclick="window.MSim.openBenchPicker(${idx}, '${cat}')">
                    <span class="text-xs font-bold text-white/50">${cat}</span>
                    <span class="text-[10px] text-white/30 mt-0.5">Tap to add</span>
                </div>`;
            }
        });
    }


    // ============================================================
    // 5. SQUAD COUNTER + VALIDATION
    // ============================================================
    function updateSquadCounter() {
        const xiCount = Object.keys(startingXI).length;
        const benchCount = Object.keys(bench).length;
        if (squadCounter) {
            squadCounter.textContent = `${xiCount}/11 Starting · ${benchCount}/7 Bench`;
        }
        if (btnSimulate) {
            btnSimulate.disabled = !(xiCount === 11 && benchCount === 7);
        }
    }
    updateSquadCounter();


    // ============================================================
    // 6. PLAYER PICKER MODAL
    // ============================================================
    function openPicker(type, index, position, category) {
        pickerTarget = { type, index, position, category };
        if (pickerSlotLabel) {
            pickerSlotLabel.textContent = type === 'xi' ? `— ${position}` : `— ${category}`;
        }

        // Pre-set position filter for convenience
        if (pickerFilterPos) {
            if (type === 'xi' && position) {
                pickerFilterPos.value = position;
            } else if (type === 'bench' && category) {
                // For bench, pre-filter to category positions
                const catPositions = CATEGORY_POSITIONS[category] || [];
                if (catPositions.length === 1) {
                    pickerFilterPos.value = catPositions[0];
                } else {
                    pickerFilterPos.value = '';
                }
            }
        }

        renderPickerGrid();
        showPickerModal();
    }

    function renderPickerGrid() {
        const usedIds = getUsedPlayerIds();
        let filtered = allPlayers.filter(p => !usedIds.has(p.id));

        // Apply search
        const q = (pickerSearch?.value || '').toLowerCase().trim();
        if (q) {
            filtered = filtered.filter(p =>
                p.name.toLowerCase().includes(q) ||
                p.nationality.toLowerCase().includes(q) ||
                p.primary_position.toLowerCase().includes(q)
            );
        }

        // Apply nationality filter
        const nat = pickerFilterNat?.value || '';
        if (nat) {
            filtered = filtered.filter(p => p.nationality === nat);
        }

        // Apply position filter
        const pos = pickerFilterPos?.value || '';
        if (pos) {
            filtered = filtered.filter(p => p.primary_position === pos);
        }

        // For bench slots, further filter by category if no explicit position filter
        if (pickerTarget?.type === 'bench' && !pos && pickerTarget.category) {
            const catPositions = CATEGORY_POSITIONS[pickerTarget.category] || [];
            if (catPositions.length > 0) {
                filtered = filtered.filter(p => catPositions.includes(p.primary_position));
            }
        }

        // Sort by overall descending
        filtered.sort((a, b) => b.overall - a.overall);

        if (!pickerGrid) return;

        if (filtered.length === 0) {
            pickerGrid.innerHTML = `<div class="col-span-full text-center py-8 text-gray-400 text-sm">No available players found</div>`;
            return;
        }

        pickerGrid.innerHTML = filtered.map(p => `
            <div class="group cursor-pointer" onclick="window.MSim.selectPlayer(${p.id})">
                <div class="relative overflow-hidden rounded-xl bg-gray-50 dark:bg-navy-800 border border-gray-200/50 dark:border-navy-700/50 hover:border-gold-500/40 transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5">
                    <div class="aspect-[3/4] player-card-img">
                        <img src="${p.frame_image_url}" alt="" class="frame-layer"
                             onerror="this.src=window.DEFAULT_FRAME_IMAGE_URL">
                        <img src="${p.player_image_url}" alt="${p.name}" class="player-layer"
                             onerror="this.src=window.DEFAULT_PLAYER_IMAGE_URL" loading="lazy">
                    </div>
                    <div class="p-1.5">
                        <h4 class="font-bold text-navy-900 dark:text-white text-[10px] sm:text-xs truncate">${p.name}</h4>
                        <div class="flex items-center justify-between mt-0.5">
                            <span class="text-[9px] text-gray-500 dark:text-gray-400">${p.primary_position}</span>
                            <span class="text-[9px] font-bold text-gold-500">${p.overall}</span>
                        </div>
                        <div class="text-[8px] text-gray-400 dark:text-gray-500 mt-0.5 truncate">${flagImgHtml(p.nationality, 10)} ${p.nationality}</div>
                    </div>
                </div>
            </div>
        `).join('');
    }

    function showPickerModal() {
        if (!pickerModal) return;
        pickerModal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        requestAnimationFrame(() => {
            pickerOverlay?.classList.add('opacity-100');
            pickerContent?.classList.add('opacity-100', 'scale-100');
            pickerContent?.classList.remove('opacity-0', 'scale-95');
        });
    }

    function closePickerModal() {
        if (!pickerModal) return;
        pickerOverlay?.classList.remove('opacity-100');
        pickerContent?.classList.remove('opacity-100', 'scale-100');
        pickerContent?.classList.add('opacity-0', 'scale-95');
        document.body.style.overflow = '';
        setTimeout(() => pickerModal.classList.add('hidden'), 250);
        pickerTarget = null;
    }

    // Picker event listeners
    pickerClose?.addEventListener('click', closePickerModal);
    pickerOverlay?.addEventListener('click', closePickerModal);
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape' && pickerModal && !pickerModal.classList.contains('hidden')) {
            closePickerModal();
        }
    });

    let pickerSearchTimeout = null;
    pickerSearch?.addEventListener('input', () => {
        clearTimeout(pickerSearchTimeout);
        pickerSearchTimeout = setTimeout(renderPickerGrid, 200);
    });
    pickerFilterNat?.addEventListener('change', renderPickerGrid);
    pickerFilterPos?.addEventListener('change', renderPickerGrid);


    // ============================================================
    // 7. PLAYER ASSIGNMENT
    // ============================================================
    function selectPlayer(playerId) {
        if (!pickerTarget) return;
        const player = allPlayers.find(p => p.id === playerId);
        if (!player) return;

        // Check not already selected
        if (getUsedPlayerIds().has(playerId)) return;

        if (pickerTarget.type === 'xi') {
            startingXI[pickerTarget.index] = player;
            renderPitch();
        } else if (pickerTarget.type === 'bench') {
            bench[pickerTarget.index] = player;
            renderBench();
        }

        updateSquadCounter();
        closePickerModal();
    }

    function removeXIPlayer(slotIndex) {
        delete startingXI[slotIndex];
        renderPitch();
        updateSquadCounter();
    }

    function removeBenchPlayer(benchIndex) {
        delete bench[benchIndex];
        renderBench();
        updateSquadCounter();
    }


    // ============================================================
    // 8. NAVIGATION BETWEEN STEPS
    // ============================================================
    btnStartBuilding?.addEventListener('click', () => {
        stepSetup.classList.add('hidden');
        stepSquad.classList.remove('hidden');
        if (formationLabel) formationLabel.textContent = selectedFormation;
        renderPitch();
        renderBench();
        updateSquadCounter();
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    btnBackSetup?.addEventListener('click', () => {
        stepSquad.classList.add('hidden');
        stepSetup.classList.remove('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });


    // ============================================================
    // 9. SIMULATE MATCH
    // ============================================================
    btnSimulate?.addEventListener('click', async () => {
        hideValidationErrors();
        btnSimulate.disabled = true;
        btnSimulate.textContent = 'Validating...';

        // Build request payload
        const xiPayload = Object.entries(startingXI).map(([idx, p]) => ({
            player_id: p.id,
            slot_index: parseInt(idx),
        }));
        const benchPayload = Object.values(bench).map(p => ({
            player_id: p.id,
        }));

        try {
            // Step 1: Validate
            const valRes = await fetch('/api/match-simulator/validate-squad', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    formation: selectedFormation,
                    starting_xi: xiPayload,
                    bench: benchPayload,
                }),
            });
            const valData = await valRes.json();

            if (!valData.valid) {
                showValidationErrors(valData.errors || ['Squad validation failed.']);
                btnSimulate.disabled = false;
                btnSimulate.textContent = 'Simulate Match ⚡';
                return;
            }

            // Step 2: Simulate
            btnSimulate.textContent = 'Simulating...';
            const simRes = await fetch('/api/match-simulator/simulate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    difficulty: selectedDifficulty,
                    formation: selectedFormation,
                    starting_xi: xiPayload,
                    bench: benchPayload,
                }),
            });
            const simData = await simRes.json();

            if (simData.error) {
                showValidationErrors([simData.error]);
                btnSimulate.disabled = false;
                btnSimulate.textContent = 'Simulate Match ⚡';
                return;
            }

            // Step 3: Play animation then show result
            stepSquad.classList.add('hidden');
            await playMatchAnimation();
            renderResult(simData);

        } catch (err) {
            console.error('Simulation error:', err);
            showValidationErrors(['Network error. Please try again.']);
            btnSimulate.disabled = false;
            btnSimulate.textContent = 'Simulate Match ⚡';
        }
    });


    // ============================================================
    // 10. MATCH ANIMATION
    // ============================================================
    async function playMatchAnimation() {
        stepAnimation.classList.remove('hidden');
        const stages = ['⚽ Kickoff', 'First Half', '🔄 Half-Time', 'Second Half', '🏁 Full-Time'];
        const delays = [500, 500, 500, 500, 500]; // ~2.5s total

        for (let i = 0; i < stages.length; i++) {
            animStage.textContent = stages[i];
            animStage.classList.remove('opacity-0');
            animStage.classList.add('opacity-100');
            await sleep(delays[i]);
            if (i < stages.length - 1) {
                animStage.classList.remove('opacity-100');
                animStage.classList.add('opacity-0');
                await sleep(150);
            }
        }
        await sleep(300);
        animStage.classList.remove('opacity-100');
        animStage.classList.add('opacity-0');
        stepAnimation.classList.add('hidden');
    }

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }


    // ============================================================
    // 11. RESULT SCREEN RENDERING
    // ============================================================
    function renderResult(data) {
        stepResult.classList.remove('hidden');
        window.scrollTo({ top: 0, behavior: 'smooth' });

        // Badge
        const badge = document.getElementById('result-badge');
        if (badge) {
            if (data.result === 'win') {
                badge.textContent = '🏆 Victory';
                badge.className = 'inline-block px-4 py-1 rounded-full text-xs font-bold uppercase tracking-widest mb-4 bg-green-500/15 text-green-600 dark:text-green-400 border border-green-500/25';
            } else if (data.result === 'loss') {
                badge.textContent = '💔 Defeat';
                badge.className = 'inline-block px-4 py-1 rounded-full text-xs font-bold uppercase tracking-widest mb-4 bg-accent-500/15 text-accent-600 dark:text-accent-400 border border-accent-500/25';
            } else {
                badge.textContent = '🤝 Draw';
                badge.className = 'inline-block px-4 py-1 rounded-full text-xs font-bold uppercase tracking-widest mb-4 bg-gray-500/15 text-gray-600 dark:text-gray-400 border border-gray-500/25';
            }
        }

        // Scores
        const userScoreEl = document.getElementById('result-user-score');
        const aiScoreEl = document.getElementById('result-ai-score');
        if (userScoreEl) userScoreEl.textContent = data.user_team.score;
        if (aiScoreEl) aiScoreEl.textContent = data.ai_team.score;

        // Stats bars
        renderStatsBars(data.user_team.stats, data.ai_team.stats);

        // Goalscorers
        renderGoalscorers('result-user-goals', data.user_team.goalscorers);
        renderGoalscorers('result-ai-goals', data.ai_team.goalscorers);

        // Substitutions
        renderSubstitutions('result-user-subs', data.user_team.substitutions);
        renderSubstitutions('result-ai-subs', data.ai_team.substitutions);

        // MOTM
        renderMOTM(data.motm, data);

        // Analysis
        const analysisEl = document.getElementById('result-analysis');
        if (analysisEl) analysisEl.textContent = data.match_analysis;
    }

    function renderStatsBars(userStats, aiStats) {
        const container = document.getElementById('result-stats');
        if (!container) return;

        const stats = [
            { label: 'Possession', user: userStats.possession, ai: aiStats.possession, suffix: '%' },
            { label: 'Shots', user: userStats.shots, ai: aiStats.shots, suffix: '' },
            { label: 'Shots on Target', user: userStats.shots_on_target, ai: aiStats.shots_on_target, suffix: '' },
        ];

        container.innerHTML = stats.map(s => {
            const total = s.user + s.ai || 1;
            const userPct = (s.user / total) * 100;
            const aiPct = (s.ai / total) * 100;
            return `
            <div class="flex items-center gap-3">
                <span class="w-12 text-right text-sm font-bold text-navy-900 dark:text-white">${s.user}${s.suffix}</span>
                <div class="flex-1 flex h-2.5 rounded-full overflow-hidden bg-gray-100 dark:bg-navy-800">
                    <div class="bg-gold-500 rounded-l-full transition-all duration-700" style="width: ${userPct}%"></div>
                    <div class="bg-navy-300 dark:bg-navy-600 rounded-r-full transition-all duration-700" style="width: ${aiPct}%"></div>
                </div>
                <span class="w-12 text-left text-sm font-bold text-navy-900 dark:text-white">${s.ai}${s.suffix}</span>
            </div>
            <p class="text-center text-[10px] text-gray-400 uppercase tracking-widest -mt-1 mb-1">${s.label}</p>
            `;
        }).join('');
    }

    function renderGoalscorers(containerId, scorers) {
        const el = document.getElementById(containerId);
        if (!el) return;
        if (!scorers || scorers.length === 0) {
            el.innerHTML = '<p class="text-gray-400 text-xs italic">No goals</p>';
            return;
        }
        el.innerHTML = scorers.map(s =>
            `<div class="flex items-center gap-2">
                <span class="text-gold-500 text-xs">⚽</span>
                <span class="font-medium">${s.name}</span>
                <span class="text-gray-400 text-xs ml-auto">${s.minute}'</span>
            </div>`
        ).join('');
    }

    function renderSubstitutions(containerId, subs) {
        const el = document.getElementById(containerId);
        if (!el) return;
        if (!subs || subs.length === 0) {
            el.innerHTML = '<p class="text-gray-400 text-xs italic">No substitutions</p>';
            return;
        }
        el.innerHTML = subs.map(s =>
            `<div class="flex items-center gap-2 text-xs sm:text-sm">
                <span class="text-green-500">▲</span>
                <span class="font-medium">${s.player_on}</span>
                <span class="text-accent-500">▼</span>
                <span class="text-gray-400">${s.player_off}</span>
                <span class="text-gray-400 ml-auto">${s.minute}'</span>
            </div>`
        ).join('');
    }

    function renderMOTM(motm, data) {
        if (!motm) return;

        const motmName = document.getElementById('motm-name');
        const motmDetails = document.getElementById('motm-details');
        const motmRating = document.getElementById('motm-rating');
        const motmFrame = document.getElementById('motm-frame');
        const motmPlayer = document.getElementById('motm-player');

        // Find the full player data for images
        const teamData = motm.team === 'user' ? data.user_team : data.ai_team;
        const playerData = teamData.starting_xi.find(p => p.name === motm.name);

        if (motmFrame && playerData) motmFrame.src = playerData.frame_image_url || window.DEFAULT_FRAME_IMAGE_URL;
        if (motmPlayer && playerData) {
            motmPlayer.src = playerData.player_image_url || window.DEFAULT_PLAYER_IMAGE_URL;
            motmPlayer.alt = motm.name;
        }

        if (motmName) motmName.textContent = motm.name;
        if (motmDetails) {
            const teamLabel = motm.team === 'user' ? 'Your Team' : 'AI Select XI';
            motmDetails.innerHTML = `${flagImgHtml(motm.nationality, 14)} ${motm.nationality} · ${motm.primary_position} · ${teamLabel}`;
        }
        if (motmRating) motmRating.textContent = motm.rating.toFixed(1);
    }


    // ============================================================
    // 12. VALIDATION ERROR DISPLAY
    // ============================================================
    function showValidationErrors(errors) {
        if (!validationErrors || !validationErrorList) return;
        validationErrorList.innerHTML = errors.map(e => `<li>• ${e}</li>`).join('');
        validationErrors.classList.remove('hidden');
    }

    function hideValidationErrors() {
        if (validationErrors) validationErrors.classList.add('hidden');
    }


    // ============================================================
    // 13. PLAY AGAIN
    // ============================================================
    btnPlayAgain?.addEventListener('click', () => {
        // Reset state
        startingXI = {};
        bench = {};
        selectedDifficulty = 'normal';
        selectedFormation = '4-3-3';

        // Reset UI
        stepResult.classList.add('hidden');
        stepSetup.classList.remove('hidden');
        btnSimulate.disabled = true;
        btnSimulate.textContent = 'Simulate Match ⚡';
        hideValidationErrors();
        renderFormationButtons();

        // Reset difficulty selection
        difficultyCards.forEach(c => {
            c.classList.remove('ring-2', 'ring-gold-500/30', 'border-gold-500/40', 'dark:border-gold-500/30', 'bg-gold-50/50', 'dark:bg-gold-500/5');
            c.classList.add('border-gray-200/50', 'dark:border-navy-800/50', 'bg-white', 'dark:bg-navy-900');
        });
        // Highlight normal
        const normalCard = document.querySelector('[data-difficulty="normal"]');
        if (normalCard) {
            normalCard.classList.remove('border-gray-200/50', 'dark:border-navy-800/50', 'bg-white', 'dark:bg-navy-900');
            normalCard.classList.add('ring-2', 'ring-gold-500/30', 'border-gold-500/40', 'dark:border-gold-500/30', 'bg-gold-50/50', 'dark:bg-gold-500/5');
        }

        window.scrollTo({ top: 0, behavior: 'smooth' });
    });


    // ============================================================
    // GLOBAL API (for onclick handlers in template)
    // ============================================================
    window.MSim = {
        onSlotClick: (slotIndex, position) => {
            openPicker('xi', slotIndex, position, getCategory(position));
        },
        openBenchPicker: (benchIndex, category) => {
            openPicker('bench', benchIndex, '', category);
        },
        selectPlayer,
        removeXIPlayer,
        removeBenchPlayer,
    };

});
