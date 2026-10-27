/**
 * Answer-first FAQ copy. Rendered on /pricing and the landing page, and
 * mirrored into the FAQPage JSON-LD in index.html — keep the two in step.
 * Each answer opens with a direct one-sentence answer (what search and AI
 * answer engines quote), then the detail.
 */
export interface FaqItem {
  q: string
  a: string
}

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
    a: 'NorAI turns a lecture video into chapter-wise study notes, a revision sheet, a quiz, flashcards and an AI tutor that answers only from that lecture, with timestamps back to the video.',
  },
  {
    q: 'Which videos can I use?',
    a: 'Paste a YouTube link or upload an MP4, MOV, MKV, AVI or WebM file. Recorded classes, NPTEL and university lectures, coaching videos and conference talks all work; NorAI is tuned for English-language lectures today.',
  },
  {
    q: 'How long does processing take?',
    a: 'NorAI shows an estimate before you start, and most lectures are ready in a few minutes. You can close the tab while it works; the finished notes appear in your library.',
  },
  {
    q: 'Is the AI tutor accurate?',
    a: 'The tutor answers from the lecture you uploaded, not from the open web, and cites the timestamp each answer comes from so you can check it against the video.',
  },
]
