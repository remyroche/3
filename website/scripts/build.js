const fs = require('fs-extra');
const path = require('path');

// Define project paths
const sourceDir = path.join(__dirname, '..', 'source');
const localesDir = path.join(__dirname, '..', 'locales');
const distDir = path.join(__dirname, '..', 'dist');

// The languages to build
const languages = ['fr', 'en']; // Add more languages as needed
const fs = require('fs-extra');
const path = require('path');

// Define project paths
const sourceDir = path.join(__dirname, '..', 'source');
const localesDir = path.join(__dirname, '..', 'locales');
const distDir = path.join(__dirname, '..', 'dist');

// The languages to build for the public site
const publicLanguages = ['fr', 'en'];
// Configurable option: whether to fail build on missing keys
const FAIL_ON_MISSING_KEYS = false; // Set to true to make build stricter

// Global error/warning collectors
let allMissingKeys = {}; // { lang: { key: count } }
let fileProcessingErrors = []; // { filePath: '...', error: '...' }

// Main build function
async function build() {
    console.log('Starting enhanced build process for Maison Trüvra website...');

    // 1. Clean the distribution directory
    await fs.emptyDir(distDir);
    console.log('Cleaned dist directory.');

    // 2. Load all translation files
    const translations = {};
    for (const lang of publicLanguages) {
        try {
            translations[lang] = await fs.readJson(path.join(localesDir, `${lang}.json`));
            allMissingKeys[lang] = {}; // Initialize missing keys tracker for each language
            console.log(`Loaded translation file for: ${lang}`);
        } catch (error) {
            const errorMessage = `Error loading translation file for ${lang}: ${error.message}`;
            console.error(errorMessage);
            fileProcessingErrors.push({ filePath: `locales/${lang}.json`, error: errorMessage });
            // Continue without this language or fail build, depending on policy
        }
    }

    // 2.1. Check for key parity between locale files (Basic Check)
    if (publicLanguages.length > 1) {
        const baseLang = publicLanguages[0];
        if (translations[baseLang]) {
            const baseKeys = new Set(Object.keys(translations[baseLang]));
            for (let i = 1; i < publicLanguages.length; i++) {
                const compareLang = publicLanguages[i];
                if (translations[compareLang]) {
                    const compareKeys = new Set(Object.keys(translations[compareLang]));
                    baseKeys.forEach(key => {
                        if (!compareKeys.has(key)) {
                            console.warn(`WARNING: Key "${key}" exists in "${baseLang}.json" but is missing in "${compareLang}.json".`);
                            if (!allMissingKeys[compareLang][key]) allMissingKeys[compareLang][key] = 0;
                            allMissingKeys[compareLang][key]++;
                        }
                    });
                    compareKeys.forEach(key => {
                        if (!baseKeys.has(key)) {
                            console.warn(`WARNING: Key "${key}" exists in "${compareLang}.json" but is missing in "${baseLang}.json".`);
                             if (!allMissingKeys[baseLang][key]) allMissingKeys[baseLang][key] = 0;
                            allMissingKeys[baseLang][key]++;
                        }
                    });
                }
            }
        }
    }


    // 3. Process Admin Panel (copy once, assumes it's mostly language-agnostic or handles i18n internally)
    const adminSourceDir = path.join(sourceDir, 'admin');
    const adminDistDir = path.join(distDir, 'admin');
    if (await fs.pathExists(adminSourceDir)) {
        try {
            await fs.copy(adminSourceDir, adminDistDir);
            console.log(`Admin panel copied to: ${path.relative(path.join(__dirname, '..'), adminDistDir)}`);
        } catch (error) {
            const errorMessage = `Error copying admin panel: ${error.message}`;
            console.error(errorMessage);
            fileProcessingErrors.push({ filePath: 'admin panel', error: errorMessage });
        }
    } else {
        console.warn('Admin source directory not found, skipping admin panel copy.');
    }

    // 4. Process each language for the public site
    for (const lang of publicLanguages) {
        if (!translations[lang]) {
            console.warn(`Skipping public site build for language '${lang}' due to missing translation file.`);
            continue;
        }
        console.log(`\n--- Building public site for language: ${lang.toUpperCase()} ---`);
        const langDistDir = path.join(distDir, lang);
        await fs.ensureDir(langDistDir);

        // Process all files and directories from the source directory (excluding admin)
        await processDirectory(sourceDir, langDistDir, lang, translations[lang], translations);
    }

    // 5. Report build summary
    console.log('\n--- Build Summary ---');
    if (fileProcessingErrors.length > 0) {
        console.error('\nFile Processing Errors Encountered:');
        fileProcessingErrors.forEach(err => console.error(`- ${err.filePath}: ${err.error}`));
    } else {
        console.log('No file processing errors.');
    }

    let totalMissingKeys = 0;
    console.log('\nMissing Translation Key Report:');
    for (const lang in allMissingKeys) {
        const missingInLang = Object.keys(allMissingKeys[lang]);
        if (missingInLang.length > 0) {
            console.warn(`Language "${lang}":`);
            missingInLang.forEach(key => {
                console.warn(`  - Key "${key}" was referenced ${allMissingKeys[lang][key]} time(s) but not found in ${lang}.json.`);
                totalMissingKeys += allMissingKeys[lang][key];
            });
        } else {
            console.log(`Language "${lang}": No missing keys detected during content processing.`);
        }
    }

    if (totalMissingKeys > 0) {
        console.warn(`\nTotal missing key references: ${totalMissingKeys}`);
        if (FAIL_ON_MISSING_KEYS) {
            console.error('Build FAILED due to missing translation keys.');
            process.exit(1);
        } else {
            console.warn('Build completed with missing key warnings.');
        }
    } else {
        console.log('No missing key references found.');
    }

    if (fileProcessingErrors.length === 0 && (!FAIL_ON_MISSING_KEYS || totalMissingKeys === 0)) {
        console.log('\n✅ Build completed successfully!');
    } else {
        console.error('\n❌ Build completed with errors/warnings.');
        if (fileProcessingErrors.length > 0) process.exit(1); // Fail if there were file processing errors
    }
}

// Function to recursively process directories (modified to exclude admin for language builds)
async function processDirectory(currentSourceDir, currentDestDir, lang, dictionary, allDictionaries) {
    await fs.ensureDir(currentDestDir);
    const items = await fs.readdir(currentSourceDir);

    for (const item of items) {
        const itemSourcePath = path.join(currentSourceDir, item);
        const itemDestPath = path.join(currentDestDir, item);

        // Skip admin directory when processing language-specific builds
        if (item === 'admin' && currentSourceDir === sourceDir) {
            console.log(`Skipping admin directory for language build: ${lang}`);
            continue;
        }

        const stats = await fs.stat(itemSourcePath);
        if (stats.isDirectory()) {
            await processDirectory(itemSourcePath, itemDestPath, lang, dictionary, allDictionaries);
        } else {
            await processFile(itemSourcePath, itemDestPath, lang, dictionary, allDictionaries);
        }
    }
}

// Function to process a single file (modified for missing key reporting and JS t() removal)
async function processFile(sourcePath, destPath, lang, dictionary, allDictionaries) {
    const ext = path.extname(sourcePath);
    const relativeSourcePath = path.relative(sourceDir, sourcePath);

    try {
        if (ext === '.html' || ext === '.js') {
            let content = await fs.readFile(sourcePath, 'utf-8');

            // Replace {{key}} placeholders in HTML
            if (ext === '.html') {
                content = content.replace(/{{\s*([\w.-]+)\s*}}/g, (match, key) => {
                    if (dictionary.hasOwnProperty(key)) {
                        return dictionary[key];
                    } else {
                        console.warn(`WARNING: Missing HTML key "${key}" in ${lang}.json for file ${relativeSourcePath}. Using placeholder: "${match}"`);
                        if (!allMissingKeys[lang][key]) allMissingKeys[lang][key] = 0;
                        allMissingKeys[lang][key]++;
                        return match; // Fallback to original match
                    }
                });
                content = content.replace(/<html lang=".*">/, `<html lang="${lang}">`);
                content = content.replace(/<meta charset=".*">/, `<meta charset="${dictionary['global.charset'] || 'UTF-8'}">`);
                // ... other HTML specific replacements ...

                // Inject all translations for runtime JS access (Option B)
                let scriptToInject = `<script>\n  window.MAISON_TRUVRA_TRANSLATIONS = ${JSON.stringify(allDictionaries)};\n  window.MAISON_TRUVRA_CURRENT_LANG = "${lang}";\n</script>`;
                content = content.replace('</head>', `${scriptToInject}\n</head>`);

            }

            // For JavaScript files, we are now relying on a runtime t() function.
            // So, we don't replace t('key') calls here anymore.
            // We might still want to inject language or specific translations if needed,
            // but the global object in HTML is often sufficient.

            await fs.writeFile(destPath, content);
            console.log(`Processed: ${path.relative(path.join(__dirname, '..'), destPath)}`);

        } else if (path.basename(sourcePath) !== '.DS_Store') {
            await fs.copy(sourcePath, destPath);
            console.log(`Copied:    ${path.relative(path.join(__dirname, '..'), destPath)}`);
        }
    } catch (error) {
        const errorMessage = `Error processing file ${relativeSourcePath}: ${error.message}`;
        console.error(errorMessage);
        fileProcessingErrors.push({ filePath: relativeSourcePath, error: errorMessage });
    }
}

// Run the build
build().catch(err => {
    console.error('Build failed with unhandled exception:', err);
    process.exit(1);
});
