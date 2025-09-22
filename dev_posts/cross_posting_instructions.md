# Cross-Posting Instructions for dev.to

## Overview
After publishing tutorials on the LaunchDarkly Docs subsite, cross-post them to dev.to to expose content to new audiences and stretch existing content further.

## Cross-Posting Process

### 1. Content Preparation
- **Remove custom Fern components** - dev.to uses standard markdown
- **Recreate all images** - Upload images directly to dev.to or use external hosting
- **Convert any special formatting** to standard markdown

### 2. Adding Canonical URL
Include canonical URL in the front matter to indicate original source and help with SEO:

```yaml
---
title: "Your Post Title"
published: true
description: "A brief description of your post"
tags: programming, tutorial, devto, launchdarkly
canonical_url: "https://docs.launchdarkly.com/path/to/original/post"
---
```

### 3. Front Matter Best Practices
- **Title**: Keep engaging and descriptive
- **Description**: Brief summary for SEO and social sharing
- **Tags**: Include relevant tags like `programming`, `tutorial`, `ai`, `launchdarkly`
- **Published**: Set to `true` when ready to publish
- **Canonical URL**: Always point back to the original LaunchDarkly docs post

### 4. Benefits
- **SEO Protection**: Search engines know the original source
- **Audience Expansion**: Reach developers who don't follow LaunchDarkly directly
- **Content Leverage**: Maximize value from existing high-quality content
- **Community Engagement**: Tap into dev.to's active developer community

### 5. Checklist Before Publishing
- [ ] Removed all Fern-specific components
- [ ] Images uploaded and displaying correctly
- [ ] Canonical URL added to front matter
- [ ] Tags are relevant and appropriately chosen
- [ ] Content reads well in standard markdown format
- [ ] Links to LaunchDarkly docs/features work correctly

## Notes
- This is manual work but worth the effort for audience expansion
- Always ensure canonical URL points to the original LaunchDarkly docs post
- Consider adding a brief intro mentioning this is cross-posted from LaunchDarkly docs