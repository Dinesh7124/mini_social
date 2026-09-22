/* ============ HELPERS ============ */
function getCookie(name) {
  const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
  return v ? v.pop() : '';
}
const CSRF = getCookie('csrftoken');

function showToast(msg) {
  const t = document.createElement('div');
  t.className = 'toast';
  t.textContent = msg;
  const container = document.getElementById('toast-container');
  if (container) container.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

function createCommentElement(author, content, isReply = false, commentId = null) {
  const div = document.createElement('div');
  div.className = 'comment' + (isReply ? ' reply' : '');
  if (commentId) div.dataset.commentId = commentId;
  const strong = document.createElement('strong');
  strong.textContent = author;
  div.appendChild(strong);
  div.appendChild(document.createTextNode(content));
  return div;
}

function linkifyHashtagsIn(el) {
  if (el.dataset.linkified) return;
  el.dataset.linkified = '1';
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  const textNodes = [];
  let node;
  while ((node = walker.nextNode())) textNodes.push(node);

  textNodes.forEach(textNode => {
    const text = textNode.nodeValue;
    if (!/#\w+/.test(text)) return;
    const frag = document.createDocumentFragment();
    let lastIndex = 0;
    const regex = /#(\w+)/g;
    let match;
    while ((match = regex.exec(text)) !== null) {
      if (match.index > lastIndex) {
        frag.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
      }
      const a = document.createElement('a');
      a.href = `/search/?q=%23${match[1]}`;
      a.textContent = '#' + match[1];
      a.style.color = 'var(--primary)';
      a.style.fontWeight = '600';
      frag.appendChild(a);
      lastIndex = regex.lastIndex;
    }
    if (lastIndex < text.length) {
      frag.appendChild(document.createTextNode(text.slice(lastIndex)));
    }
    textNode.parentNode.replaceChild(frag, textNode);
  });
}

/* ============ THEME ============ */
const themeBtn = document.getElementById('theme-toggle');
const savedTheme = localStorage.getItem('theme') || 'light';
document.documentElement.setAttribute('data-theme', savedTheme);
if (themeBtn) {
  themeBtn.textContent = savedTheme === 'dark' ? '☀️' : '🌙';
  themeBtn.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    themeBtn.textContent = next === 'dark' ? '☀️' : '🌙';
  });
}

/* ============ COMPOSER ============ */
const postBtn = document.getElementById('post-btn');
const postContent = document.getElementById('post-content');
const charCount = document.getElementById('char-count');
const imageInput = document.getElementById('image-input');
const videoInput = document.getElementById('video-input');
const imagePreview = document.getElementById('image-preview');

function updatePostBtn() {
  const hasText = postContent?.value.trim().length > 0;
  const hasImage = imageInput?.files[0];
  const hasVideo = videoInput?.files[0];
  if (postBtn) postBtn.disabled = !(hasText || hasImage || hasVideo);
}

if (postContent) {
  postContent.addEventListener('input', () => {
    charCount.textContent = postContent.value.length;
    updatePostBtn();
  });
}

if (imageInput) {
  imageInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      imagePreview.innerHTML = '';
      const img = document.createElement('img');
      img.src = ev.target.result;
      imagePreview.appendChild(img);
      updatePostBtn();
    };
    reader.readAsDataURL(file);
  });
}

if (videoInput) {
  videoInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const sizeMB = file.size / (1024 * 1024);
    if (sizeMB > 50) {
      showToast('⚠️ Video too large (max 50MB)');
      videoInput.value = '';
      return;
    }
    showToast(`📹 Video selected (${sizeMB.toFixed(1)}MB)`);
    updatePostBtn();
  });
}

if (postBtn) {
  postBtn.addEventListener('click', async () => {
    const content = postContent.value.trim();
    const image = imageInput?.files[0];
    const video = videoInput?.files[0];
    if (!content && !image && !video) return;

    const formData = new FormData();
    if (content) formData.append('content', content);
    if (image) formData.append('image', image);
    if (video) formData.append('video', video);

    postBtn.disabled = true;
    const res = await fetch('/api/post/', {
      method: 'POST',
      headers: { 'X-CSRFToken': CSRF },
      body: formData
    });
    if (res.ok) {
      showToast('Post shared! 🎉');
      setTimeout(() => location.reload(), 400);
    } else {
      showToast('Failed to post');
      postBtn.disabled = false;
    }
  });

  postContent.addEventListener('keydown', (e) => {
    if (e.ctrlKey && e.key === 'Enter') postBtn.click();
  });
}

/* ============ REACTIONS ============ */
const reactionEmojis = {
  like: '❤️',
  love: '😍',
  haha: '😂',
  wow: '😮',
  sad: '😢',
  angry: '😡',
};

// Hover / long-press to show picker
document.querySelectorAll('.reaction-wrapper').forEach(wrapper => {
  const picker = wrapper.querySelector('.reaction-picker');
  const btn = wrapper.querySelector('.reaction-btn');
  if (!picker || !btn) return;
  let pressTimer;

  const show = () => picker.classList.add('show');
  const hide = () => picker.classList.remove('show');

  btn.addEventListener('touchstart', () => {
    pressTimer = setTimeout(show, 300);
  });
  btn.addEventListener('touchend', () => clearTimeout(pressTimer));

  wrapper.addEventListener('mouseenter', show);
  wrapper.addEventListener('mouseleave', () => setTimeout(hide, 250));
});

// Pick a reaction
document.addEventListener('click', async (e) => {
  const option = e.target.closest('.reaction-option');
  if (!option) return;

  const wrapper = option.closest('.reaction-wrapper');
  const btn = wrapper.querySelector('.reaction-btn');
  const postId = btn.dataset.postId;
  const reaction = option.dataset.reaction;

  const res = await fetch(`/api/reaction/${postId}/`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': CSRF,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({ reaction })
  });

  const data = await res.json();
  if (res.ok) {
    btn.querySelector('.reaction-icon').textContent = data.reaction ? reactionEmojis[data.reaction] : '🤍';
    btn.querySelector('.reaction-count').textContent = Object.values(data.counts).reduce((a, b) => a + b, 0);
    btn.className = 'action-btn reaction-btn';
    if (data.reaction) btn.classList.add(`reacted-${data.reaction}`);
    wrapper.querySelector('.reaction-picker').classList.remove('show');
  }
});

// Quick like on click (no long press)
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.reaction-btn');
  if (!btn || e.target.closest('.reaction-option')) return;

  const postId = btn.dataset.postId;
  const res = await fetch(`/api/reaction/${postId}/`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': CSRF,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({ reaction: 'like' })
  });

  const data = await res.json();
  if (res.ok) {
    btn.querySelector('.reaction-icon').textContent = data.reaction ? reactionEmojis[data.reaction] : '🤍';
    btn.querySelector('.reaction-count').textContent = Object.values(data.counts).reduce((a, b) => a + b, 0);
    btn.className = 'action-btn reaction-btn';
    if (data.reaction) btn.classList.add(`reacted-${data.reaction}`);
  }
});

/* ============ COMMENT ============ */
document.addEventListener('submit', async (e) => {
  const form = e.target.closest('.comment-form');
  if (!form) return;
  e.preventDefault();
  const input = form.querySelector('input');
  const content = input.value.trim();
  if (!content) return;

  const res = await fetch(`/api/comment/${form.dataset.postId}/`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': CSRF,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({ content })
  });
  const data = await res.json();
  if (res.ok) {
    const div = createCommentElement(data.author, data.content, false, data.id);
    form.parentElement.insertBefore(div, form);
    input.value = '';
    showToast('Comment added 💬');
  }
});

/* ============ REPLY ============ */
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.reply-btn');
  if (!btn) return;
  const text = prompt('Reply:');
  if (!text || !text.trim()) return;

  const res = await fetch(`/api/comment/${btn.dataset.postId}/`, {
    method: 'POST',
    headers: {
      'X-CSRFToken': CSRF,
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({
      content: text.trim(),
      parent_id: btn.dataset.commentId
    })
  });
  const data = await res.json();
  if (res.ok) {
    const parent = btn.closest('.comment');
    const reply = createCommentElement(data.author, data.content, true, data.id);
    parent.appendChild(reply);
    showToast('Reply added 💬');
  }
});

/* ============ FOLLOW ============ */
const followBtn = document.getElementById('follow-btn');
if (followBtn) {
  followBtn.addEventListener('click', async () => {
    const res = await fetch(`/api/follow/${followBtn.dataset.username}/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': CSRF }
    });
    const data = await res.json();
    if (res.ok) {
      followBtn.classList.toggle('following', data.following);
      followBtn.textContent = data.following ? 'Following ✓' : 'Follow +';
      document.getElementById('followers-count').textContent = data.followers_count;
      showToast(data.following ? 'Now following!' : 'Unfollowed');
    }
  });
}

/* ============ POST MENU ============ */
document.addEventListener('click', (e) => {
  const menuBtn = e.target.closest('.menu-btn');
  document.querySelectorAll('.menu-dropdown').forEach(m => {
    if (!menuBtn || m !== menuBtn.nextElementSibling) m.classList.remove('show');
  });
  if (menuBtn) menuBtn.nextElementSibling.classList.toggle('show');
});

document.addEventListener('click', async (e) => {
  const editLink = e.target.closest('.edit-post');
  const deleteLink = e.target.closest('.delete-post');

  if (editLink) {
    e.preventDefault();
    const postId = editLink.dataset.postId;
    const postEl = document.querySelector(`.post[data-post-id="${postId}"]`);
    const contentEl = postEl.querySelector('.post-content');
    const newContent = prompt('Edit post:', contentEl ? contentEl.textContent : '');
    if (newContent && newContent.trim()) {
      const res = await fetch(`/api/post/${postId}/edit/`, {
        method: 'POST',
        headers: {
          'X-CSRFToken': CSRF,
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({ content: newContent.trim() })
      });
      if (res.ok) {
        if (contentEl) contentEl.textContent = newContent.trim();
        showToast('Post updated ✏️');
      }
    }
  }

  if (deleteLink) {
    e.preventDefault();
    const postId = deleteLink.dataset.postId;
    if (!confirm('Delete this post?')) return;
    const res = await fetch(`/api/post/${postId}/delete/`, {
      method: 'POST',
      headers: { 'X-CSRFToken': CSRF }
    });
    if (res.ok) {
      document.querySelector(`.post[data-post-id="${postId}"]`).remove();
      showToast('Post deleted 🗑️');
    }
  }
});

/* ============ SAVE POST ============ */
document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.save-btn');
  if (!btn) return;
  const res = await fetch(`/api/save/${btn.dataset.postId}/`, {
    method: 'POST',
    headers: { 'X-CSRFToken': CSRF }
  });
  const data = await res.json();
  if (res.ok) {
    btn.classList.toggle('saved', data.saved);
    btn.innerHTML = data.saved ? '🔖 <span>Saved</span>' : '📑 <span>Save</span>';
    showToast(data.saved ? 'Post saved 🔖' : 'Removed from saved');
  }
});

/* ============ HASHTAG LINKIFY ============ */
document.querySelectorAll('.post-content').forEach(linkifyHashtagsIn);

/* ============ INFINITE SCROLL ============ */
let currentPage = 1;
let loadingPosts = false;
let noMorePosts = false;

const feedContainer = document.getElementById('feed');
const loadMoreBtn = document.getElementById('load-more-btn');
const sentinel = document.getElementById('load-more-sentinel');

async function loadMorePosts() {
  if (loadingPosts || noMorePosts || !feedContainer) return;
  loadingPosts = true;
  if (loadMoreBtn) loadMoreBtn.textContent = 'Loading...';

  const nextPage = currentPage + 1;
  try {
    const res = await fetch(`/?page=${nextPage}`, {
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    });
    const data = await res.json();

    if (data.html) {
      const temp = document.createElement('div');
      temp.innerHTML = data.html;
      while (temp.firstChild) feedContainer.appendChild(temp.firstChild);
      currentPage = nextPage;
      feedContainer.querySelectorAll('.post-content').forEach(linkifyHashtagsIn);
    }

    if (!data.has_next) {
      noMorePosts = true;
      if (loadMoreBtn) loadMoreBtn.style.display = 'none';
      const end = document.createElement('p');
      end.style.cssText = 'text-align:center;color:var(--text-muted);padding:2rem 1rem;font-size:.95rem;';
      end.textContent = '🎉 You\'re all caught up!';
      feedContainer.appendChild(end);
    } else {
      if (loadMoreBtn) loadMoreBtn.textContent = 'Load More ↓';
    }
  } catch (err) {
    console.error('Failed to load more posts', err);
    if (loadMoreBtn) loadMoreBtn.textContent = 'Retry';
  }
  loadingPosts = false;
}

if (loadMoreBtn) loadMoreBtn.addEventListener('click', loadMorePosts);

if (sentinel && 'IntersectionObserver' in window) {
  const observer = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) loadMorePosts();
  }, { rootMargin: '200px' });
  observer.observe(sentinel);
}

/* ============ SUGGESTIONS ============ */
async function loadSuggestions() {
  const box = document.getElementById('suggestions-box');
  const list = document.getElementById('suggestions-list');
  if (!box || !list) return;

  try {
    const res = await fetch('/api/suggestions/');
    const data = await res.json();
    if (!data.users || data.users.length === 0) return;

    list.innerHTML = '';
    data.users.forEach(u => {
      const card = document.createElement('div');
      card.className = 'suggestion-card';

      const avatar = document.createElement('div');
      avatar.className = 'avatar';
      if (u.avatar) {
        const img = document.createElement('img');
        img.src = u.avatar;
        img.style.cssText = 'width:100%;height:100%;border-radius:50%;object-fit:cover;';
        avatar.appendChild(img);
      } else {
        avatar.textContent = u.username[0].toUpperCase();
      }

      const name = document.createElement('strong');
      name.textContent = u.username;

      const followers = document.createElement('small');
      followers.textContent = u.followers + ' followers';

      const btn = document.createElement('button');
      btn.className = 'suggestion-follow';
      btn.dataset.username = u.username;
      btn.textContent = 'Follow';

      card.appendChild(avatar);
      card.appendChild(name);
      card.appendChild(followers);
      card.appendChild(btn);
      list.appendChild(card);
    });

    box.style.display = 'block';
  } catch (err) {
    console.error('Suggestions failed', err);
  }
}

loadSuggestions();

document.addEventListener('click', async (e) => {
  const btn = e.target.closest('.suggestion-follow');
  if (!btn) return;
  const res = await fetch(`/api/follow/${btn.dataset.username}/`, {
    method: 'POST',
    headers: { 'X-CSRFToken': CSRF }
  });
  const data = await res.json();
  if (res.ok) {
    btn.textContent = 'Following ✓';
    btn.classList.add('following');
    showToast('Now following!');
    setTimeout(() => {
      const card = btn.closest('.suggestion-card');
      if (card) card.remove();
    }, 800);
  }
});

/* ============ LIVE NOTIFICATION BELL ============ */
const notifBell = document.getElementById('notif-bell');

if (notifBell) {
  setInterval(async () => {
    try {
      const res = await fetch('/api/unread/');
      const data = await res.json();

      let badge = document.getElementById('notif-badge');
      if (data.count > 0) {
        if (!badge) {
          badge = document.createElement('span');
          badge.id = 'notif-badge';
          badge.className = 'badge';
          notifBell.appendChild(badge);
        }
        const prev = badge.textContent;
        badge.textContent = data.count;
        if (prev !== String(data.count)) {
          badge.animate([
            { transform: 'scale(1)' },
            { transform: 'scale(1.4)' },
            { transform: 'scale(1)' },
          ], { duration: 400, easing: 'ease-out' });
        }
      } else if (badge) {
        badge.remove();
      }
    } catch (err) {
      // silent fail
    }
  }, 15000);
}