// --- Language Management ---
let currentLang = 'fr'; // Default language

/**
 * Sets the current language for the site.
 * @param {string} lang - The language code ('fr' or 'en').
 */
function setLanguage(lang) {
    if (['fr', 'en'].includes(lang)) {
        currentLang = lang;
        localStorage.setItem('preferredLang', lang);
        console.log(`Language set to: ${currentLang}`);
    } else {
        console.warn(`Unsupported language: ${lang}. Defaulting to ${currentLang}.`);
    }
}

/**
 * Gets the preferred language from localStorage or browser settings.
 * @returns {string} The language code ('fr' or 'en').
 */
function getInitialLanguage() {
    const storedLang = localStorage.getItem('preferredLang');
    if (storedLang && ['fr', 'en'].includes(storedLang)) {
        return storedLang;
    }
    const browserLang = navigator.language.split('-')[0];
    if (['fr', 'en'].includes(browserLang)) {
        return browserLang;
    }
    return 'fr'; // Default
}

// Initialize currentLang on script load
currentLang = getInitialLanguage();

/**
 * Retrieves translated text for a given field from an item object.
 * @param {object} item - The object containing translatable fields (e.g., product or category).
 * @param {string} fieldKey - The key of the field to translate (e.g., 'name', 'description').
 * @returns {string} The translated text or a fallback string.
 */
function getTranslatedText(item, fieldKey) {
    if (!item || typeof item !== 'object') return `Invalid item for ${fieldKey}`;
    const field = item[fieldKey];
    if (!field) return `[${fieldKey} missing]`;
    if (typeof field === 'string') return field; // Field is not multilingual
    if (field[currentLang]) return field[currentLang];
    if (field['fr']) return field['fr']; // Fallback to French
    if (field['en']) return field['en']; // Fallback to English
    return `[${fieldKey} translation N/A]`;
}

/**
 * Helper function to set language and reload the page.
 * To be used by language switcher buttons.
 * @param {string} lang - The language code ('fr' or 'en').
 */
function setLanguageAndReload(lang) {
    setLanguage(lang);
    window.location.reload();
}

// --- Data Fetching ---
async function fetchData(jsonPath) {
    try {
        const response = await fetch(jsonPath);
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status} for ${jsonPath}`);
        return await response.json();
    } catch (error) {
        console.error(`Could not load data from ${jsonPath}:`, error);
        return null;
    }
}