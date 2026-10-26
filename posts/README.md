# How to write a blog post

Takes about 2 minutes. No coding.

1. On GitHub, open this **posts** folder and click **Add file → Create new file**.
2. Name the file with the date and a short title, ending in `.md`, for example:
   `2026-11-02-china-leads-october.md`
3. Paste this at the top and fill it in:

   ```
   ---
   title: Your post title
   date: 2026-11-02
   author: Your Name
   summary: One sentence shown on the blog page.
   tags: analysis, countries
   ---
   ```

4. Write the post underneath. Use `## ` for headings, `- ` for bullet points,
   `**bold**`, and `[link text](https://...)`. See `_template.md` for more examples.
5. Click **Commit changes**. The website rebuilds by itself and your post is online
   in about 1 minute at `researchboard.net/blog/`.

**Pictures:** upload them into `posts/images/`, then write
`![description](images/file-name.png)` in your post.

**Drafts:** add `draft: true` to the header to keep a post hidden until it's ready.

**Edit or delete:** open the post file, click the ✏️ pencil to edit or the ⋯ menu to
delete, then commit. The site updates automatically.

**Daily reports** in `posts/daily/` are written automatically every morning. You
don't need to touch them.
