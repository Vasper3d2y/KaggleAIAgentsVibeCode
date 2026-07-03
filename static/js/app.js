// Application State
let releases = [];
let filteredReleases = [];
let selectedRelease = null;
let currentCategoryFilter = 'All';
let currentSearchQuery = '';

// DOM Elements
const feedContainer = document.getElementById('feed-timeline');
const searchInput = document.getElementById('search-input');
const clearSearchBtn = document.getElementById('clear-search-btn');
const refreshBtn = document.getElementById('refresh-btn');
const refreshIcon = document.getElementById('refresh-icon');
const lastUpdatedText = document.getElementById('last-updated-text');
const categoryTabs = document.querySelectorAll('.filter-tab');

// Stats Elements
const statAll = document.getElementById('stat-all');
const statFeature = document.getElementById('stat-feature');
const statChange = document.getElementById('stat-change');
const statDeprecation = document.getElementById('stat-deprecation');
const statCards = document.querySelectorAll('.stat-card.filter-trigger');

// Composer Elements
const composerPlaceholder = document.getElementById('composer-placeholder');
const composerForm = document.getElementById('composer-form');
const composerSelectedTitle = document.getElementById('composer-selected-title');
const tweetTextarea = document.getElementById('tweet-textarea');
const charCount = document.getElementById('char-count');
const charWarning = document.getElementById('char-warning');
const tweetSubmitBtn = document.getElementById('tweet-submit-btn');
const tweetPreviewText = document.getElementById('tweet-preview-text');
const resetTweetBtn = document.getElementById('reset-tweet-btn');
const selectedIndicator = document.getElementById('selected-indicator');

// Toast Element
const toast = document.getElementById('toast');
const toastMessage = document.getElementById('toast-message');

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
    fetchReleases();
    setupEventListeners();
});

// Event Listeners setup
function setupEventListeners() {
    // Refresh Button click
    refreshBtn.addEventListener('click', () => {
        fetchReleases(true);
    });

    // Search Input keyup
    searchInput.addEventListener('input', (e) => {
        currentSearchQuery = e.target.value.trim().toLowerCase();
        
        if (currentSearchQuery) {
            clearSearchBtn.style.display = 'block';
        } else {
            clearSearchBtn.style.display = 'none';
        }
        
        applyFiltersAndSearch();
    });

    // Clear Search button click
    clearSearchBtn.addEventListener('click', () => {
        searchInput.value = '';
        currentSearchQuery = '';
        clearSearchBtn.style.display = 'none';
        applyFiltersAndSearch();
    });

    // Category Tabs click
    categoryTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            categoryTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            currentCategoryFilter = tab.dataset.category;
            applyFiltersAndSearch();
        });
    });

    // Stats Cards click (which acts as a filter shortcut)
    statCards.forEach(card => {
        card.addEventListener('click', () => {
            const category = card.dataset.category;
            
            // Sync with tabs selection
            categoryTabs.forEach(t => {
                if (t.dataset.category === category) {
                    t.classList.add('active');
                } else {
                    t.classList.remove('active');
                }
            });
            
            currentCategoryFilter = category;
            applyFiltersAndSearch();
        });
    });

    // Tweet text change
    tweetTextarea.addEventListener('input', () => {
        updateCharacterCount();
        updateTweetPreview();
    });

    // Reset Tweet Draft button click
    resetTweetBtn.addEventListener('click', () => {
        if (selectedRelease) {
            const draft = generateTweetDraft(selectedRelease);
            tweetTextarea.value = draft;
            updateCharacterCount();
            updateTweetPreview();
            showToast('Draft reset to original template');
        }
    });

    // Submit Tweet click
    tweetSubmitBtn.addEventListener('click', () => {
        shareOnTwitter();
    });
}

// Fetch Release Notes
async function fetchReleases(forceRefresh = false) {
    // Show Loading
    setLoadingState(true);
    
    try {
        const url = forceRefresh ? '/api/releases?refresh=true' : '/api/releases';
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.success) {
            releases = data.releases;
            lastUpdatedText.textContent = `Feed updated: ${data.last_updated}`;
            
            // Update stats
            calculateStats();
            
            // Render the feed
            applyFiltersAndSearch();
            
            if (forceRefresh) {
                showToast('Release notes successfully updated!');
            }
        } else {
            console.error('API Error:', data.error);
            showErrorState(`Failed to fetch: ${data.error}`);
        }
    } catch (err) {
        console.error('Fetch Error:', err);
        showErrorState('Network error while fetching release notes.');
    } finally {
        setLoadingState(false);
    }
}

// Loading Spinner Switch
function setLoadingState(isLoading) {
    if (isLoading) {
        refreshBtn.disabled = true;
        refreshIcon.classList.add('spin-icon');
        
        // If no releases are loaded yet, display main loading
        if (releases.length === 0) {
            feedContainer.innerHTML = `
                <div class="loading-state">
                    <div class="spinner-large"></div>
                    <p>Loading latest BigQuery release notes...</p>
                </div>
            `;
        }
    } else {
        refreshBtn.disabled = false;
        refreshIcon.classList.remove('spin-icon');
    }
}

// Error state display
function showErrorState(message) {
    feedContainer.innerHTML = `
        <div class="empty-state">
            <i class="fa-solid fa-circle-exclamation" style="color: #ea4335;"></i>
            <h3>Oops, something went wrong</h3>
            <p>${message}</p>
            <button onclick="fetchReleases(true)" class="btn btn-primary" style="margin-top: 1rem;">
                <i class="fa-solid fa-arrows-rotate"></i> Try Again
            </button>
        </div>
    `;
}

// Calculate Stats for Dashboard counters
function calculateStats() {
    const total = releases.length;
    
    // Count specific categories
    const features = releases.filter(r => r.category.toLowerCase() === 'feature').length;
    const changes = releases.filter(r => r.category.toLowerCase() === 'change').length;
    const deprecations = releases.filter(r => r.category.toLowerCase() === 'deprecation').length;
    
    // Animate stats values
    animateValue(statAll, total);
    animateValue(statFeature, features);
    animateValue(statChange, changes);
    animateValue(statDeprecation, deprecations);
}

// Counter animation
function animateValue(obj, end, duration = 500) {
    let start = parseInt(obj.textContent) || 0;
    if (start === end) return;
    let range = end - start;
    let current = start;
    let increment = end > start ? 1 : -1;
    let stepTime = Math.abs(Math.floor(duration / range));
    stepTime = Math.max(stepTime, 10); // cap at 10ms speed
    
    let timer = setInterval(function() {
        current += increment;
        obj.textContent = current;
        if (current == end) {
            clearInterval(timer);
        }
    }, stepTime);
}

// Filters & search logic
function applyFiltersAndSearch() {
    filteredReleases = releases.filter(release => {
        // 1. Category Filter
        let matchesCategory = false;
        if (currentCategoryFilter === 'All') {
            matchesCategory = true;
        } else if (currentCategoryFilter === 'Other') {
            const knownCats = ['feature', 'change', 'deprecation', 'fix'];
            matchesCategory = !knownCats.includes(release.category.toLowerCase());
        } else {
            matchesCategory = release.category.toLowerCase() === currentCategoryFilter.toLowerCase();
        }
        
        // 2. Keyword Search
        let matchesSearch = true;
        if (currentSearchQuery) {
            const titleMatch = release.date.toLowerCase().includes(currentSearchQuery);
            const categoryMatch = release.category.toLowerCase().includes(currentSearchQuery);
            const contentMatch = release.text_content.toLowerCase().includes(currentSearchQuery);
            matchesSearch = titleMatch || categoryMatch || contentMatch;
        }
        
        return matchesCategory && matchesSearch;
    });
    
    renderFeed();
}

// Render feed timeline to layout
function renderFeed() {
    if (filteredReleases.length === 0) {
        feedContainer.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-folder-open"></i>
                <h3>No Release Notes Found</h3>
                <p>Try refining your search terms or category selection filters.</p>
            </div>
        `;
        return;
    }
    
    feedContainer.innerHTML = '';
    
    filteredReleases.forEach(release => {
        const isSelected = selectedRelease && selectedRelease.id === release.id;
        
        const card = document.createElement('article');
        card.className = `release-card ${isSelected ? 'selected' : ''}`;
        card.id = `card-${release.id}`;
        
        // Category normalizer for css styling
        let catClass = 'general';
        const catLower = release.category.toLowerCase();
        if (catLower === 'feature') catClass = 'feature';
        else if (catLower === 'change') catClass = 'change';
        else if (catLower === 'deprecation') catClass = 'deprecation';
        else if (catLower === 'fix') catClass = 'fix';
        
        card.innerHTML = `
            <div class="release-card-header">
                <div class="badge-and-date">
                    <span class="category-badge ${catClass}">${release.category}</span>
                    <span class="release-date">${release.date}</span>
                </div>
                <button class="card-select-btn" onclick="selectForTweet('${release.id}')">
                    <i class="${isSelected ? 'fa-solid fa-circle-check' : 'fa-regular fa-square'}"></i>
                    <span>${isSelected ? 'Selected' : 'Select to Tweet'}</span>
                </button>
            </div>
            
            <div class="release-description">
                ${release.description}
            </div>
            
            <div class="release-card-footer">
                ${release.link ? `
                    <a href="${release.link}" target="_blank" rel="noopener noreferrer" class="external-link">
                        <i class="fa-solid fa-up-right-from-square"></i> Open in release notes
                    </a>
                ` : ''}
            </div>
        `;
        
        // Clicking anywhere on card (except buttons & links) selects it
        card.addEventListener('click', (e) => {
            if (e.target.tagName !== 'A' && !e.target.closest('a') && 
                e.target.tagName !== 'BUTTON' && !e.target.closest('button')) {
                selectForTweet(release.id);
            }
        });
        
        feedContainer.appendChild(card);
    });
}

// Select update to compose tweet
window.selectForTweet = function(id) {
    const item = releases.find(r => r.id === id);
    if (!item) return;
    
    // Toggle check
    if (selectedRelease && selectedRelease.id === item.id) {
        // Deselect
        selectedRelease = null;
        composerForm.style.display = 'none';
        composerPlaceholder.style.display = 'flex';
        selectedIndicator.textContent = 'No Entry Selected';
        selectedIndicator.classList.remove('selected');
        
        // Remove class selection from cards
        document.querySelectorAll('.release-card').forEach(c => c.classList.remove('selected'));
        document.querySelectorAll('.card-select-btn i').forEach(i => {
            i.className = 'fa-regular fa-square';
        });
        document.querySelectorAll('.card-select-btn span').forEach(s => {
            s.textContent = 'Select to Tweet';
        });
    } else {
        selectedRelease = item;
        
        // Update all cards selection styles
        document.querySelectorAll('.release-card').forEach(c => {
            const cardId = c.id.replace('card-', '');
            if (cardId === item.id) {
                c.classList.add('selected');
                const btnIcon = c.querySelector('.card-select-btn i');
                if (btnIcon) btnIcon.className = 'fa-solid fa-circle-check';
                const btnText = c.querySelector('.card-select-btn span');
                if (btnText) btnText.textContent = 'Selected';
            } else {
                c.classList.remove('selected');
                const btnIcon = c.querySelector('.card-select-btn i');
                if (btnIcon) btnIcon.className = 'fa-regular fa-square';
                const btnText = c.querySelector('.card-select-btn span');
                if (btnText) btnText.textContent = 'Select to Tweet';
            }
        });
        
        // Setup composer widget
        selectedIndicator.textContent = 'Active Draft';
        selectedIndicator.classList.add('selected');
        composerSelectedTitle.textContent = `${item.date} - ${item.category}`;
        composerPlaceholder.style.display = 'none';
        composerForm.style.display = 'block';
        
        // Draft Tweet text
        const draftText = generateTweetDraft(item);
        tweetTextarea.value = draftText;
        
        updateCharacterCount();
        updateTweetPreview();
        
        // Scroll composer into view on mobile
        if (window.innerWidth <= 1024) {
            composerForm.scrollIntoView({ behavior: 'smooth' });
        }
    }
};

// Auto generate tweet content based on category and description length
function generateTweetDraft(item) {
    let emoji = '📢';
    const cat = item.category.toLowerCase();
    
    if (cat === 'feature') emoji = '🚀';
    else if (cat === 'change') emoji = '⚙️';
    else if (cat === 'deprecation') emoji = '⚠️';
    else if (cat === 'fix') emoji = '🛠️';
    
    const header = `${emoji} BigQuery ${item.category} (${item.date}):\n\n`;
    const hashtags = `\n\n#GoogleCloud #BigQuery`;
    
    // Character budgets
    // X allows 280 chars. 
    // Link usually occupies ~23 chars (t.co wrapper)
    // Hashtags + Header = X chars.
    // Let's compute text budgets safely:
    const linkPlaceholder = item.link ? `\n\nRead more: ${item.link}` : '';
    const staticLength = header.length + hashtags.length + (item.link ? 35 : 0);
    const availableLength = 280 - staticLength - 10; // extra padding
    
    let textBody = item.text_content;
    
    // Clean up double spacing and formatting artifacts
    textBody = textBody.replace(/\s+/g, ' ');
    
    if (textBody.length > availableLength) {
        textBody = textBody.substring(0, availableLength - 3) + '...';
    }
    
    return `${header}${textBody}${linkPlaceholder}${hashtags}`;
}

// Live character counter logic
function updateCharacterCount() {
    const text = tweetTextarea.value;
    
    // X link counts: X's t.co replaces all links with a 23-char short link
    // We should estimate actual length accurately for the user.
    let estimatedLength = text.length;
    
    // Regex for URL matching
    const urlRegex = /https?:\/\/[^\s]+/g;
    const urls = text.match(urlRegex) || [];
    
    urls.forEach(url => {
        // Subtract original link size and add 23 characters standard
        estimatedLength = estimatedLength - url.length + 23;
    });
    
    charCount.textContent = estimatedLength;
    
    // Warning styling flags
    const countBox = charCount.parentElement;
    if (estimatedLength > 280) {
        countBox.className = 'character-count-box danger';
        charWarning.style.display = 'inline';
        tweetSubmitBtn.disabled = true;
    } else if (estimatedLength >= 250) {
        countBox.className = 'character-count-box warning';
        charWarning.style.display = 'none';
        tweetSubmitBtn.disabled = false;
    } else {
        countBox.className = 'character-count-box';
        charWarning.style.display = 'none';
        tweetSubmitBtn.disabled = false;
    }
}

// Live preview sync
function updateTweetPreview() {
    const text = tweetTextarea.value;
    
    // Transform text with HTML link representation for beautiful visual preview
    const urlRegex = /(https?:\/\/[^\s]+)/g;
    let previewHTML = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(urlRegex, '<span class="preview-url">$1</span>')
        .replace(/(#[a-zA-Z0-9_]+)/g, '<span class="preview-hashtag">$1</span>');
        
    tweetPreviewText.innerHTML = previewHTML || '<i>Start typing your tweet or select an update...</i>';
}

// Share via X web intent
function shareOnTwitter() {
    const tweetText = tweetTextarea.value;
    if (!tweetText) return;
    
    const intentUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(tweetText)}`;
    
    showToast('Opening X / Twitter...');
    window.open(intentUrl, '_blank', 'width=550,height=420,toolbar=0,status=0');
}

// Toast indicator notifications
function showToast(message) {
    toastMessage.textContent = message;
    toast.style.display = 'flex';
    
    // Reset timer
    if (window.toastTimer) {
        clearTimeout(window.toastTimer);
    }
    
    window.toastTimer = setTimeout(() => {
        toast.style.display = 'none';
    }, 3000);
}
