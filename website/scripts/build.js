const fs = require('fs-extra');
const path = require('path');

// Define project paths
const sourceDir = path.join(__dirname, '..', 'source');
const localesDir = path.join(__dirname, '..', 'locales');
const distDir = path.join(__dirname, '..', 'dist');

// The languages to build
const languages = ['fr', 'en'];

// Main build function
async function build() {
    console.log('Starting build process...');

    // 1. Clean the distribution directory
    await fs.emptyDir(distDir);
    console.log('Cleaned dist directory.');

    // 2. Load all translation files
    const translations = {};
    for (const lang of languages) {
        translations[lang] = await fs.readJson(path.join(localesDir, `${lang}.json`));
    }
    console.log('Loaded translation files for:', languages.join(', '));

    // 3. Process each language
    for (const lang of languages) {
        console.log(`\n--- Building for language: ${lang.toUpperCase()} ---`);
        const langDistDir = path.join(distDir, lang);
        await fs.ensureDir(langDistDir);

        // Get all files from the source directory
        const files = await fs.readdir(sourceDir);

        for (const file of files) {
            const sourcePath = path.join(sourceDir, file);
            const destPath = path.join(langDistDir, file);
            const stats = await fs.stat(sourcePath);

            if (stats.isDirectory()) {
                // Recursively process subdirectories (like /admin, /js, /videos)
                await processDirectory(sourcePath, destPath, lang, translations[lang]);
            } else {
                // Process files in the root source directory
                await processFile(sourcePath, destPath, lang, translations[lang]);
            }
        }
    }

    console.log('\n✅ Build completed successfully!');
}

// Function to recursively process directories
async function processDirectory(source, dest, lang, dictionary) {
    await fs.ensureDir(dest);
    const items = await fs.readdir(source);
    for (const item of items) {
        const itemSourcePath = path.join(source, item);
        const itemDestPath = path.join(dest, item);
        const stats = await fs.stat(itemSourcePath);

        if (stats.isDirectory()) {
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

        // Replace {{key}} placeholders
        content = content.replace(/{{\s*([\w.-]+)\s*}}/g, (match, key) => {
            return dictionary[key] || match; // Return key if translation not found
        });
        
        // In JS files, replace t('key') with the translated string literal
        if (ext === '.js') {
            content = content.replace(/t\(['"`]([\w.-]+)['"`]\)/g, (match, key) => {
                 // Return the translated string, properly escaped for JavaScript
                return JSON.stringify(dictionary[key] || key);
            });
        }

        // For HTML files, also set the lang attribute
        if (ext === '.html') {
            content = content.replace(/<html lang=".*">/, `<html lang="${lang}">`);
        }

        await fs.writeFile(destPath, content);
        console.log(`Processed: ${destPath}`);

    } else {
        // For other files (CSS, images, videos, etc.), just copy them
        await fs.copy(sourcePath, destPath);
        console.log(`Copied:    ${destPath}`);
    }
}


// Run the build
build().catch(err => {
    console.error('Build failed:', err);
    process.exit(1);
});
