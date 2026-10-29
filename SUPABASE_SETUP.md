# Supabase production setup

Checklist for the production Supabase project. Written 2026-10-29 from the current code and a check of project `eaaeujkkiflzunrwyfzx`.

## 0. Do first, on the current project

RLS is off on all `public` tables, and the `anon` role can read `users` and update `subscriptions`. The anon key ships in the frontend bundle, so anyone could call the REST API (`/rest/v1/...`) to read user emails and payments, or give themselves Pro.

The frontend only uses `supabase.auth.*`, and the backend connects as `postgres`, which bypasses RLS. Locking the tables breaks nothing.

1. **Project Settings → Data API:** turn the Data API off, or remove `public` from the exposed schemas.
2. **SQL Editor:** run
   ```sql
   do $$ declare t text; begin
     for t in select tablename from pg_tables where schemaname = 'public' loop
       execute format('alter table public.%I enable row level security', t);
       execute format('revoke all on public.%I from anon, authenticated', t);
     end loop;
   end $$;
   alter default privileges in schema public revoke all on tables from anon, authenticated;
   ```
3. **Database → Advisors → Security Advisor:** no "RLS disabled" errors should be left.

## 1. Create the project

- Pick the **same region as the VPS** (US East or EU for the western audience). The current Sydney DB makes `/usage` take ~4.5 s.
- Use the **Pro plan**. Free projects pause when idle and have no daily backups.
- Set a long DB password of **letters and digits only**. `&` and `#` break shell and driver URL parsing.
- Turn on MFA on the Supabase account.

## 2. Database

- Use the **Session pooler, port 5432**, in the backend env:
  `DATABASE_URL=postgresql+asyncpg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres`
- Start the backend once. Alembic creates the tables on startup.
- Then repeat **step 0** on the new project.
- **Database → Settings:** keep SSL enforcement on, and set Network Restrictions to allow only the VPS IP.

## 3. Keys and JWT

- Backend: set `SUPABASE_URL`. ES256 tokens are verified against its JWKS. `SUPABASE_JWT_SECRET` is only needed for a legacy HS256 project.
- Frontend build args: `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` (the anon/publishable key).
- Never use the `service_role`/secret key anywhere. The app doesn't need it.

## 4. Authentication → Sign In / Providers

- **Email:** on, with **Confirm email ON**, and a minimum password length of 8 or more.
- **Anonymous sign-ins: OFF.** The frontend doesn't use them; guests are handled by the backend.
- **Google:**
  1. Google Cloud Console → APIs & Services → Credentials → OAuth client ID (Web application).
  2. Authorized redirect URI: `https://<ref>.supabase.co/auth/v1/callback`.
  3. Fill in the OAuth consent screen (app name, domain, privacy policy URL), then **publish** it. In Testing mode, only listed test users can sign in.
  4. Paste the client ID and secret into the Supabase Google provider.

## 5. Authentication → URL Configuration

- **Site URL:** `https://yourdomain.com`
- **Redirect URLs:** `https://yourdomain.com/**`. That covers `/app` after sign-up, `/reset-password`, and the return to the current page after Google sign-in.
- Leave `localhost` out of the production project. Use the old project as dev, after step 0.

## 6. Authentication → Emails

- Set up custom SMTP (Resend, Postmark or SES) with a sender like `no-reply@yourdomain.com`. Verify the domain with SPF, DKIM and DMARC.
- The built-in mailer sends only a few emails an hour, which would break sign-up and "Forgot password".
- Once custom SMTP works, raise the email limit under **Authentication → Rate Limits**.
- Update the **Confirm signup** and **Reset password** templates with the product name and copy.

## 7. Authentication → Attack Protection

- Leave **CAPTCHA off** until the frontend sends a Turnstile token. Turning it on now rejects every sign-up.
- Turn on leaked-password protection if the plan includes it.

## 8. Verify on the live domain

1. Sign up: the confirmation email arrives from your domain, and its link lands on `/app` signed in.
2. Google sign-in works with an account that isn't a test user.
3. "Forgot password" sends an email, and `/reset-password` sets a new password.
4. `curl "https://<ref>.supabase.co/rest/v1/subscriptions" -H "apikey: <anon key>"` returns an error, not rows.
5. The Security Advisor shows no errors.

There's nothing to migrate: the old project only holds test accounts, including `norai-e2e-test@example.com`, which is set to Pro.

## Code follow-ups

- Put the step 0 SQL in an Alembic migration, so every new project and table gets it.
- Hide the Google button until the provider is configured.
- Add Cloudflare Turnstile to sign-up and sign-in, so CAPTCHA can be turned on.
