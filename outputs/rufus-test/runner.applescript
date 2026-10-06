on run argv
    set testId to item 1 of argv
    set promptB64 to item 2 of argv
    set screenshotPath to item 3 of argv
    set outputText to ""

    tell application "Safari"
        set targetTab to current tab of window id 4473

        do JavaScript "(() => { const b = document.querySelector('button[aria-label=\"Start a new chat\"]'); if (b) b.click(); return !!b; })()" in targetTab
        delay 1

        set sendScript to "(() => { const t = document.querySelector('#rufus-text-area'); const b = document.querySelector('#rufus-submit-button'); if (!t || !b) return 'missing'; const s = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set; s.call(t, atob('" & promptB64 & "')); t.dispatchEvent(new Event('input', {bubbles:true})); t.dispatchEvent(new Event('change', {bubbles:true})); b.click(); return 'sent'; })()"
        do JavaScript sendScript in targetTab

        repeat with pollIndex from 1 to 20
            delay 2
            set stillGenerating to do JavaScript "(() => { const c = document.querySelector('#rufus-conversation-container'); const tx = c?.innerText || ''; const n = Array.from(c?.querySelectorAll('*') || []).map(e => (e.innerText || '').trim()).filter(x => x.length > 40 && x.length < 320 && x.endsWith('Add to cart')).length; return String(tx.includes('Rufus is currently generating a response') || n === 0); })()" in targetTab
            if stillGenerating is "false" then exit repeat
        end repeat

        set extractScript to "(() => { const c = document.querySelector('#rufus-conversation-container'); const tx = c?.innerText || ''; const raw = Array.from(c?.querySelectorAll('*') || []).map(e => (e.innerText || '').trim()).filter(x => x.length > 40 && x.length < 320 && x.endsWith('Add to cart')); const cards = [...new Set(raw)]; const qs = Array.from(document.querySelectorAll('.rufus-customer-text-wrap')).map(e => (e.innerText || '').trim()); return JSON.stringify({id:'" & testId & "', questions:qs, products:cards.slice(0,5), conversation:tx.slice(0,14000)}); })()"
        set outputText to do JavaScript extractScript in targetTab

        do JavaScript "(() => { const c = document.querySelector('#rufus-conversation-container'); if (c) c.scrollTop = 0; return !!c; })()" in targetTab
        delay 1
    end tell

    do shell script "/usr/sbin/screencapture -x -l 4473 " & quoted form of screenshotPath

    return outputText
end run
