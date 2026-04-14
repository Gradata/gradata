# Gradata Supabase Email Templates

Branded V3 Dark Cinematic email templates for Supabase Auth. Email-client-safe (inline CSS, table layout, no external fonts, no JS, no background images).

Sender: `Gradata <noreply@gradata.ai>`
Theme: dark `#0C1120` background, `#F8FAFC` text, CTA gradient `#3A82FF → #7C3AED`.

## Templates

| File | Supabase template | Subject line | Variables used |
|---|---|---|---|
| `confirm-signup.html` | **Confirm signup** | `Confirm your Gradata account` | `{{ .ConfirmationURL }}` |
| `magic-link.html` | **Magic Link** | `Sign in to Gradata` | `{{ .ConfirmationURL }}`, `{{ .Email }}` |
| `change-email.html` | **Change Email Address** | `Confirm your new email` | `{{ .ConfirmationURL }}`, `{{ .Email }}` |
| `reset-password.html` | **Reset Password** | `Reset your Gradata password` | `{{ .ConfirmationURL }}`, `{{ .Email }}` |
| `invite-user.html` | **Invite user** | `You've been invited to a Gradata workspace` | `{{ .ConfirmationURL }}`, `{{ .Email }}`, `{{ .Role }}`, `{{ .InvitedAt }}` |
| `reauthentication.html` | **Reauthentication** | `Confirm it's you` | `{{ .Token }}`, `{{ .ConfirmationURL }}`, `{{ .Email }}` |

> `{{ .Role }}` and `{{ .InvitedAt }}` require passing `role` and `invited_at` in the invite metadata (`supabase.auth.admin.inviteUserByEmail(email, { data: { role: 'admin' } })`). If omitted, they render blank — the template still reads cleanly.

## How to install (5 steps)

1. **Open Supabase dashboard** → project → **Authentication** → **Email Templates**.
2. **Set sender** under *Authentication* → *Email* → SMTP settings. Set *Sender name* to `Gradata` and *Sender email* to `noreply@gradata.ai`.
3. **For each template above**: click the template name, paste the **Subject line** from the table, then paste the full HTML body from the corresponding file in this directory. Keep `{{ .ConfirmationURL }}` and other `{{ .Variable }}` tokens literal — Supabase substitutes them at send time.
4. **Save** each template. Supabase renders a live preview — confirm the dark gradient button shows with white text.
5. **Test** by triggering each flow (sign up a throwaway email, request a magic link, reset a password, invite a teammate, run a sensitive action that triggers reauthentication). Check Gmail, Outlook, and Apple Mail — all three render the table layout consistently.

## Preview locally

Open any `.html` file directly in a browser. The `{{ ... }}` tokens show literally — that's expected; Supabase replaces them at send time.

## Design notes

- **Layout**: nested `<table>` elements only (Outlook-safe). Max width 560px.
- **CSS**: all inline (Gmail strips `<style>` tags).
- **Font stack**: `system-ui` — no external font loading.
- **CTA button**: gradient background set on a `<td>` wrapper so clients that strip anchor backgrounds still show color. Minimum 140px wide, 12px vertical padding.
- **Fallback link**: bare URL in monospace below each button so the email works even if the button fails to render.
- **Dark mode**: uses explicit `#0C1120` / `#F8FAFC` rather than CSS variables. Some clients (Outlook, older iOS Mail) force light mode — the template reads fine on light backgrounds too because button color and text contrast are absolute.
- **No images**: Gmail blocks remote images by default. The Gradata wordmark is rendered as styled text.

## Updating templates

Edit the HTML file, then re-paste into Supabase. Keep each file under 250 lines — these are transactional emails, not marketing.
