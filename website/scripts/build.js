const fs = require('fs-extra');
const path = require('path');

// Define project paths
const sourceDir = path.join(__dirname, '..', 'source');
const localesDir = path.join(__dirname, '..', 'locales');
const distDir = path.join(__dirname, '..', 'dist');

// The languages to build
const languages = ['fr', 'en']; // Add more languages as needed

// Main build function
async function build() {
    console.log('Starting build process for Maison Trüvra website...');

    // 1. Clean the distribution directory
    await fs.emptyDir(distDir);
    console.log('Cleaned dist directory.');

    // 2. Load all translation files
    const translations = {};
    for (const lang of languages) {
        try {
            translations[lang] = await fs.readJson(path.join(localesDir, `${lang}.json`));
            console.log(`Loaded translation file for: ${lang}`);
        } catch (error) {
            console.error(`Error loading translation file for ${lang}: ${error.message}`);
            // Optionally, decide if build should fail or continue with missing translations
            // For now, it will try to proceed, and missing keys will use the placeholder.
        }
    }
    
    // 3. Process each language
    for (const lang of languages) {
        if (!translations[lang]) {
            console.warn(`Skipping build for language '${lang}' due to missing translation file.`);
            continue;
        }
        console.log(`\n--- Building for language: ${lang.toUpperCase()} ---`);
        const langDistDir = path.join(distDir, lang);
        await fs.ensureDir(langDistDir);

        // Process all files and directories from the source directory
        await processDirectory(sourceDir, langDistDir, lang, translations[lang]);
    }

    console.log('\n✅ Build completed successfully!');
}

// Function to recursively process directories
async function processDirectory(currentSourceDir, currentDestDir, lang, dictionary) {
    await fs.ensureDir(currentDestDir);
    const items = await fs.readdir(currentSourceDir);

    for (const item of items) {
        const itemSourcePath = path.join(currentSourceDir, item);
        const itemDestPath = path.join(currentDestDir, item);
        const stats = await fs.stat(itemSourcePath);

        if (stats.isDirectory()) {
            // Skip special directories like 'data' or 'admin' if they shouldn't be directly copied or processed this way for each lang
            // For this project, 'admin' and 'data' in 'source' are likely common or handled differently.
            // The current script structure implies 'admin' and 'data' are copied as-is into each lang folder.
            // If 'admin' has its own i18n, it would need a separate build or handling.
            // For now, we assume all subdirectories in 'source' are part of the public site structure.
            await processDirectory(itemSourcePath, itemDestPath, lang, dictionary);
        } else {
            await processFile(itemSourcePath, itemDestPath, lang, dictionary);
        }
    }
}

// Function to process a single file
async function processFile(sourcePath, destPath, lang, dictionary) {
    const ext = path.extname(sourcePath);

    // Process HTML and JS files for translation
    if (ext === '.html' || ext === '.js') {
        let content = await fs.readFile(sourcePath, 'utf-8');

        // Replace {{key.subkey}} placeholders in HTML and JS comments/strings if needed
        content = content.replace(/{{\s*([\w.-]+)\s*}}/g, (match, key) => {
            // Simple key lookup, does not handle nested objects from key like 'public.nav.home'
            // The locale files are flat, so this should work.
            return dictionary[key] || match; 
        });
        
        // In JS files, replace t('key') with the translated string literal
        // This ensures that UI strings in JavaScript are also statically translated.
        if (ext === '.js') {
            content = content.replace(/t\(['"`]([\w.-]+)['"`](?:,\s*\{[^}]*\})?\)/g, (match, key) => {
                // Basic replacement, doesn't handle interpolation object in t(key, { replacements })
                // For simple keys, this is fine. For interpolated strings, they should be handled
                // by constructing the string at runtime or using more complex build-time replacement.
                const translatedString = dictionary[key] || key; // Fallback to key if not found
                return JSON.stringify(translatedString); // Properly escape for JS string literal
            });
        }

        // For HTML files, also set the lang attribute
        if (ext === '.html') {
            content = content.replace(/<html lang=".*">/, `<html lang="${lang}">`);
            // Ensure charset and viewport are also processed if they use placeholders
            content = content.replace(/<meta charset=".*">/, `<meta charset="${dictionary['global.charset'] || 'UTF-8'}">`);
            content = content.replace(/<meta name="viewport" content=".*">/, `<meta name="viewport" content="${dictionary['global.viewport'] || 'width=device-width, initial-scale=1.0'}">`);
        }

        await fs.writeFile(destPath, content);
        console.log(`Processed: ${path.relative(path.join(__dirname, '..'), destPath)}`);

    } else if (path.basename(sourcePath) !== '.DS_Store') { // Exclude .DS_Store and other unwanted files
        // For other files (CSS, images, videos, fonts, data JSONs etc.), just copy them
        // This will copy admin/, data/, videos/, etc. into each language directory.
        try {
            await fs.copy(sourcePath, destPath);
            console.log(`Copied:    ${path.relative(path.join(__dirname, '..'), destPath)}`);
        } catch (copyError) {
            console.error(`Error copying ${sourcePath} to ${destPath}: ${copyError.message}`);
        }
    }
}

// Run the build
build().catch(err => {
    console.error('Build failed:', err);
    process.exit(1);
});
