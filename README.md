# EPUB TOC Tap Issue Fixer

## Problem

On some Kobo devices, tapping the screen while reading an EPUB unexpectedly jumps back to the Table of Contents (TOC), while swiping works normally.

This is **not a device or settings issue**, but a problem inside the EPUB file itself.

---

## What’s Happening

The behavior:

- Tap → jumps to TOC  
- Swipe → normal page turn  

This strongly indicates:

- The EPUB contains **internal hyperlinks (`<a href="...">`)**
- These links point to the **Table of Contents**
- A **tap triggers links**, while a swipe ignores them

In some cases, even large areas (like chapter headers) are wrapped in these links, making it feel like *any tap* causes the jump.

---

## Root Cause

EPUB files are essentially HTML documents. That means:

- Any element (text, headings, images) can be wrapped in:
  ```html
  <a href="...">
  ```
- E-readers treat taps like clicks on these elements

If a heading or large block is linked to the TOC, tapping it triggers navigation.

### Typical Causes

- Bad conversion (e.g. PDF → EPUB)
- Publisher formatting errors
- Broken or duplicated TOC structures
- Invisible or oversized clickable elements via CSS

---

## Why Calibre Doesn’t Fix It

Calibre is excellent for:

- Format conversion
- Metadata cleanup
- Structural fixes

However:

- It does **not rewrite internal HTML logic**
- It will not remove problematic links like:
  ```html
  <a href="toc.xhtml">...</a>
  ```

So:
- EPUB → EPUB conversion often does nothing
- “Polish” does not fix link behavior

---

## Why Swiping Still Works

- Swipe = page navigation gesture (ignores links)  
- Tap = activates element → triggers hyperlink  

---

## Solution

### 1. Workaround

- Disable tap page turns
- Use swipe-only navigation

---

### 2. Convert to KePub

Kobo’s internal format sometimes handles navigation differently and may ignore problematic links.

---

### 3. Manual Fix (Recommended)

Open the EPUB in an editor (e.g. Calibre Editor) and:

1. Search for:
   ```html
   <a href="...toc..."
   ```
2. Identify links inside headings like:
   ```html
   <h1><a href="B1004_toc.xhtml#...">...</a></h1>
   ```
3. Remove the `<a>` wrapper while keeping the content:
   ```html
   <h1>...</h1>
   ```

This directly fixes the issue.

---

### 4. Automated Fix (This Repository)

This project provides a Python script that:

- Scans EPUB files
- Detects TOC links inside headings
- Removes only the problematic `<a>` wrappers
- Preserves all other content

---

### 5. Real-World Issue Encountered

During development, some EPUB files could not be processed because:

- The EPUB (ZIP container) contained filenames with non-UTF-8 encoding (e.g. Chinese characters)
- Standard tools like Python’s `zipfile` and even 7-Zip failed with decoding or header errors

**Solution:**

- Running a simple **EPUB → EPUB conversion in Calibre** fixed the container structure
- After that, the script worked correctly and was able to clean the book

---

### 6. Alternative: Replace the EPUB

If the file is heavily broken:

- Get a different version
- Avoid poor PDF → EPUB conversions

---

## Summary

**Cause:**
- Broken or misplaced internal hyperlinks pointing to the TOC

**Effect:**
- Tapping triggers navigation to TOC

**Fix:**
- Remove or rewrite those links

---

## Notes

Some EPUBs may contain additional structural issues (e.g. malformed ZIP containers or encoding problems), which require repair before editing.

---

## Credits

- The cleanup script was generated with the help of ChatGPT
- Debugging and refinement were done based on real-world EPUB issues

---

## Contributing

If you encounter edge cases (different link patterns, unusual EPUB structures), feel free to open an issue or submit a fix.
