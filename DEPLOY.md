# GitHub Pages Deployment Guide

## Step-by-Step Deployment

### Prerequisites
- GitHub account
- Git installed on your computer
- All files ready in the project folder

### Steps

#### 1. Create a GitHub Repository

1. Go to [GitHub.com](https://github.com)
2. Click **"New"** to create a new repository
3. Name it: `data-viz-generator` (or your preferred name)
4. Description: "Data Visualization Tool for Marketing"
5. Choose **Public** (so it's accessible)
6. Click **"Create repository"**

#### 2. Push Files to GitHub

In your terminal, navigate to the project folder:

```bash
cd "/Users/GMCOC/Data Visualization Generator"
```

Initialize git and push:

```bash
# Initialize git repository
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit: Data visualization tool"

# Add GitHub as remote (replace USERNAME with your username)
git remote add origin https://github.com/USERNAME/data-viz-generator.git

# Rename branch to main (if needed)
git branch -M main

# Push to GitHub
git push -u origin main
```

#### 3. Enable GitHub Pages

1. Go to your repository on GitHub
2. Click **Settings** (top right)
3. In the left menu, click **Pages**
4. Under "Build and deployment":
   - Source: Select **Deploy from a branch**
   - Branch: Select **main** (or **master**)
   - Folder: Select **/ (root)**
5. Click **Save**

GitHub will show: *"Your site is live at: https://USERNAME.github.io/data-viz-generator/"*

#### 4. Verify Deployment

1. Wait 1-2 minutes for GitHub to deploy
2. Visit: `https://USERNAME.github.io/data-viz-generator/`
3. Tool should be live and functional!

### Updating Data Quarterly

When you have new Excel files:

1. Replace the files in the `Data/` folder on your computer
2. Run the Python script:
   ```bash
   python3 process_data.py
   ```
3. Commit and push changes:
   ```bash
   git add .
   git commit -m "Update data: Q[X] 2026"
   git push
   ```
4. GitHub Pages automatically updates within 1-2 minutes

### Sharing with Marketing Team

Once live, share the link: `https://USERNAME.github.io/data-viz-generator/`

Your marketing team can:
- Access it from any device with a browser
- No installation or setup required
- No VPN or special access needed
- Works on desktop, tablet, and mobile

### Troubleshooting Deployment

**Problem: "404 Not Found" after deployment**
- Solution: Wait 2-3 minutes for GitHub to process
- Check that repository is **Public** (not Private)
- Verify Settings → Pages shows correct branch

**Problem: CSV files not loading**
- Solution: Check that `Data/processed/` folder exists with CSV files
- Make sure files are committed and pushed to GitHub

**Problem: Charts don't display**
- Solution: Check browser console (F12 → Console tab) for errors
- Ensure column names match between HTML and CSV

**Problem: Chart.js library not loading**
- Solution: Check your internet connection (CDN requires internet)
- Try a different browser

### Making the Tool Public

The tool is already public on GitHub Pages! To make it even more discoverable:

1. **Add to GitHub Profile**
   - Add repository link to your GitHub bio
   - This helps team members find it

2. **Create a GitHub Release**
   ```bash
   git tag -a v1.0 -m "Initial release"
   git push origin v1.0
   ```

3. **Write a Good README**
   - We've included `README.md` - it auto-displays on GitHub
   - Marketing team can read it without opening the tool

### Continuous Deployment Tips

- Keep data files organized in `Data/` folder
- Always test locally before pushing
- Use meaningful commit messages for tracking changes
- Consider backing up old data files (optional but recommended)

### Advanced: Custom Domain (Optional)

If your company has a custom domain:

1. Go to Settings → Pages
2. Under "Custom domain", enter your domain
3. Add DNS CNAME record (GitHub provides instructions)

Example: `https://data-viz.yourcompany.com/`

### Support Resources

- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [GitHub Guides](https://guides.github.com/)
- [Markdown Guide](https://www.markdownguide.org/)

---

## Summary

Your data visualization tool is now:
✅ Built and tested locally
✅ Ready for GitHub deployment
✅ Accessible to your marketing team via a public URL
✅ Will auto-update when data changes and you push updates

**Total setup time:** ~5-10 minutes

---

**Need help?** Refer to the README.md or QUICK_START.md files.
