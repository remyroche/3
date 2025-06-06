const ejs = require('ejs');
const fs = require('fs-extra');
const path = require('path');
const glob = require('glob');

const sourceDir = path.join(__dirname, '../source');
const distDir = path.join(__dirname, '../dist');
const localesDir = path.join(__dirname, '../locales');
const langs = ['fr', 'en'];
const translations = {};

// 1. Load all translations
langs.forEach(lang => {
    const translationPath = path.join(localesDir, `${lang}.json`);
    if (fs.existsSync(translationPath)) {
        translations[lang] = JSON.parse(fs.readFileSync(translationPath, 'utf-8'));
    } else {
        console.error(`Error: Translation file not found for language: ${lang}`);
        process.exit(1);
    }
});

// 2. Clean and create distribution directory
fs.emptyDirSync(distDir);

// 3. Process each language
langs.forEach(lang => {
    const langDistDir = path.join(distDir, lang);
    fs.mkdirpSync(langDistDir);

    console.log(`Building for language: ${lang}`);

    // Create a translation helper function for the current language
    const t = (key) => {
        return translations[lang][key] || `[${key}]`; // Return key if not found
    };

    // 4. Find all HTML files in the source directory (including subdirectories)
    const files = glob.sync('**/*.html', { cwd: sourceDir });

    files.forEach(file => {
        const sourcePath = path.join(sourceDir, file);
        const destPath = path.join(langDistDir, file);
        
        console.log(`  Processing ${file}...`);

        const template = fs.readFileSync(sourcePath, 'utf-8');
        
        // Data to be passed to the EJS template
        const templateData = {
            t,                      // Translation function
            lang,                   // Current language code ('fr' or 'en')
            pagePath: file.replace(/\\/g, '/'), // Relative path for language switcher
            ...translations[lang]   // Spread all translations for direct access if needed
        };

        const html = ejs.render(template, templateData, {
            // Provide a root for includes to work correctly
            root: sourceDir,
            // Pass the filename for better error reporting and include resolution
            filename: sourcePath
        });

        // Ensure the destination directory exists
        fs.mkdirpSync(path.dirname(destPath));
        fs.writeFileSync(destPath, html);
    });

    // 5. Copy static assets (CSS, JS, images, etc.) for each language
    console.log(`  Copying assets for ${lang}...`);
    const assets = ['css', 'js', 'assets', 'admin', 'pro/css', 'pro/js']; // Add other asset folders here
    assets.forEach(assetDir => {
        const sourceAssetPath = path.join(sourceDir, assetDir);
        const destAssetPath = path.join(langDistDir, assetDir);
        if (fs.existsSync(sourceAssetPath)) {
            fs.copySync(sourceAssetPath, destAssetPath);
        }
    });
});

console.log('Build finished successfully!');
