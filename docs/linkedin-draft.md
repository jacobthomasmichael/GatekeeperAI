# LinkedIn Post Draft

---

Here is another AI related post you didn't ask for. But this one might actually be about something happening inside your company right now.

Someone on your team built an AI app. Maybe a chatbot to handle internal questions, a tool that summarizes customer emails, or something to automate a report that used to take two hours. Smart person, good intentions, genuinely useful.

But if you asked where it's deployed, who reviewed it, or what data it can access — would you get a clear answer? Or would it be something like "it's on my laptop" or "I set it up in my personal cloud account"?

That's the quiet risk. **Your employees are building AI tools faster than IT and security can keep up.** And right now, most companies don't have a good answer to: what's actually running, where is it, and what can it touch?

The options today aren't great:
- Lock everything down and kill the momentum
- Let it run and hope nothing goes wrong
- Try to review it all manually, which doesn't scale

So I built **GatekeeperAI** — an open source, self-hosted platform that sits between your team and production.

Here's how it works in plain English:

Someone builds an AI app and submits it. Gatekeeper automatically checks it for things like hardcoded passwords, exposed customer data, and connections to outside services. That report lands in a review queue. Security or IT looks it over, approves it or sends it back with feedback. Approved apps deploy. Everything else doesn't run.

The whole thing lives on your own servers. Nothing goes to a third-party cloud. Your team keeps building — security finally has visibility.

It's early, it's open source, and I'd love to hear from anyone thinking about this problem.

→ https://github.com/jacobthomasmichael/GatekeeperAI

#CyberSecurity #ShadowIT #EnterpriseAI #OpenSource

---
*Draft — adjust tone/details before posting*
