/**
 * Answer-first FAQ copy. Rendered on /pricing and the landing page, and
 * mirrored into the FAQPage JSON-LD and llms.txt by vite-plugin-seo.
 * Each answer opens with a direct one-sentence answer (what search and AI
 * answer engines quote), then the detail.
 */
export interface FaqItem {
  q: string
  a: string
}

/** Free allowance; mirrors backend config FREE_MONTHLY_MINUTES (NORAI_FREE_MINUTES). */
export const FREE_MINUTES = 60

/** NorAI launches free-only: these replace the paid-pass FAQ on public pages. */
export const FREE_FAQ: FaqItem[] = [
  {
    q: 'Is NorAI free?',
    a: `Yes. Every account gets ${FREE_MINUTES} lecture-minutes every 30 days with every feature included: notes, revision sheet, quiz, flashcards, mind map and the AI tutor. There is no paid plan and no credit card to enter.`,
  },
  {
    q: 'What counts as a lecture-minute?',
    a: `One minute of the video you process. A 45-minute lecture uses 45 of your ${FREE_MINUTES} minutes. Opening its notes, quiz, flashcards or tutor again afterwards costs nothing.`,
  },
  {
    q: 'What happens when I run out of minutes?',
    a: 'You can keep studying everything you already processed; only new lectures wait. Your minutes reset 30 days after your current period started, and NorAI shows the reset date in the app.',
  },
  {
    q: 'Why is there a monthly limit?',
    a: 'Turning a video into notes uses real AI compute for every minute of it. A monthly allowance per account is how NorAI stays free for everyone.',
  },
]

/**
 * Paid-pass FAQ from the India launch plan (rupees, UPI, Razorpay). Only shown
 * when the backend reports payments_enabled; rewrite for the target market
 * before turning payments on.
 */
export const PRICING_FAQ: FaqItem[] = [
  {
    q: 'How much does NorAI cost in India?',
    a: 'NorAI is free for 45 lecture-minutes every 30 days; paid passes are ₹149 (Starter, 5 hours) and ₹449 (Pro, 20 hours) for 30 days. Prices are in rupees, inclusive of all taxes.',
  },
  {
    q: 'Is it a subscription? Will I be charged automatically?',
    a: 'No. Each plan is a one-time 30-day pass, so nothing renews or auto-debits. When a pass ends you drop back to the Free plan, and you can buy another pass whenever you need one.',
  },
  {
    q: 'Which payment methods can I use?',
    a: 'UPI (Google Pay, PhonePe, Paytm, BHIM and any UPI app), debit and credit cards, netbanking and popular wallets. Payments are processed by Razorpay; NorAI never sees your card or UPI PIN.',
  },
  {
    q: 'What counts as a lecture-minute?',
    a: 'One minute of the video you upload. A 50-minute lecture uses 50 minutes of your pass, and re-opening its notes, quiz, flashcards or tutor afterwards is free.',
  },
  {
    q: 'What happens to unused minutes if I buy again?',
    a: 'They carry over. Buying another pass while one is active adds the new minutes to what you have left; buying the same plan also extends the end date by 30 days.',
  },
  {
    q: 'Can I get a refund?',
    a: 'Yes, within 7 days of purchase if you have not used the pass. Email support from the address you signed up with and the refund goes back to the original payment method in 5–7 working days.',
  },
]

export const PRODUCT_FAQ: FaqItem[] = [
  {
    q: 'What does NorAI do?',
    a: 'NorAI turns a lecture video into chapter-by-chapter study notes, a revision sheet, a quiz, flashcards and an AI tutor that answers only from that lecture, with timestamps back to the video.',
  },
  {
    q: 'What can I use?',
    a: 'Upload an MP4, MOV, MKV, AVI or WebM recording, a PDF, Word file, slide deck or text file, or paste a Google Drive or web link. Recorded classes, university lectures, online courses, conference talks and course readings all work. NorAI works best on English-language material.',
  },
  {
    q: 'How long does processing take?',
    a: 'Most lectures are ready in a few minutes; NorAI shows the length and the minutes it will use before you start. You can close the tab while it works, and the finished lecture appears in your library.',
  },
  {
    q: 'Is the AI tutor accurate?',
    a: 'The tutor answers from the lecture you processed, not from the open web, and cites the timestamp each answer comes from so you can check it against the video. If the lecture does not cover something, it says so.',
  },
  {
    q: 'How is NorAI different from asking ChatGPT about a video?',
    a: 'NorAI reads the whole lecture, transcript and slides, and builds a complete study set from it before you ask anything. The tutor is grounded in that one lecture and links every answer to the moment in the video, so it does not fill gaps with things your professor never said.',
  },
]

/** The landing page's FAQ section (and its FAQPage JSON-LD). */
export const HOME_FAQ: FaqItem[] = [...PRODUCT_FAQ, FREE_FAQ[0], FREE_FAQ[2]]
