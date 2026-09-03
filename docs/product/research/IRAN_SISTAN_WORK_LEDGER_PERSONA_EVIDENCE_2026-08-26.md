# Iran and Sistan Work-Ledger Persona Evidence

**Research cutoff:** 2026-08-26
**Status:** Research input for product design, not market validation and not a
description of implemented product capability.
**Scope:** Lived constraints that should shape a realistic composite persona
for the prospective conversational work ledger described in
`docs/product/CONVERSATIONAL_WORK_LEDGER_HANDOFF.md`.

## Executive conclusion

The most defensible persona is not “a digitally illiterate shopkeeper.” It is a
competent, phone-first worker or small-business operator whose attention is
consumed by price volatility, thin cash flow, interrupted infrastructure,
relationship-based obligations, and several incomplete information channels.
The product must earn trust by reducing memory work immediately while keeping
every financial interpretation visible, reversible, and user-confirmed.

The owner's observation that many local businesses in Sistan and Baluchestan
do not perform even simple routine recording is a valuable **local discovery
hypothesis**, but this research did not find recent province-level evidence
that can support generalizing it to the whole province. Scenario design should
therefore test several actual practices—memory only, paper notebook, chat
history, bank SMS, and basic software—instead of treating non-recording as a
fixed cultural trait.

## Evidence that should shape the role

### 1. Economic shock is an operating condition, not background color

- The IMF's Iran country page, using its July 2026 World Economic Outlook
  update, projects **-5.4% real GDP growth** and **68.9% average consumer-price
  inflation** for 2026. These are forecasts, not household observations, and
  should be used as evidence of an extreme uncertainty regime rather than as a
  precise description of any one person's price experience. ([IMF, accessed
  2026-08-26](https://www.imf.org/en/countries/irn))
- The World Bank currently estimates that GDP contracted **2.7% in the Iranian
  year ending 2026-03-20** and links the downturn to conflict, intensified
  sanctions, trade disruption, water and energy shortages, and weakened
  investment. It also expects high inflation and declining real incomes to
  suppress domestic demand. ([World Bank, accessed
  2026-08-26](https://www.worldbank.org/ext/en/country/iran))
- In the Iran Chamber of Commerce's summer 1404 business-environment survey,
  the national index worsened from **5.95 in spring to 6.09** (10 is worst).
  Participating businesses identified unpredictable input/product prices,
  difficult bank finance, unstable rules and procedures, energy constraints,
  and tax-assessment practices among the most adverse conditions. ([Iran
  Chamber of Commerce, 2025-11-02](https://otaghiranonline.ir/news/87814/%D9%85%D8%AD%DB%8C%D8%B7-%DA%A9%D8%B3%D8%A8-%D9%88%DA%A9%D8%A7%D8%B1-%D8%AF%D8%B1-%D9%81%D8%B5%D9%84-%D8%AA%D8%A7%D8%A8%D8%B3%D8%AA%D8%A7%D9%86-%D9%86%D8%A7%D9%85%D8%B3%D8%A7%D8%B9%D8%AF%D8%AA%D8%B1-%D8%B4%D8%AF-%D8%B4%D8%A7%D8%AE%D8%B5-%D9%85%D9%84%DB%8C-%D8%A8%D9%87-6-09))

**Persona inference:** the role thinks in short horizons. Quotes can expire,
payments arrive partially, the same transfer can mean a sale, debt collection,
capital injection, or family transfer, and “profit” is not observable from bank
inflow alone. The character should often care more about “What must I remember
today?” and “Who still owes what?” than about a formal monthly report.

### 2. Sistan and Baluchestan adds livelihood and infrastructure variance

- UNDP describes Sistan and Baluchestan as facing acute water stress after
  decades of drought, with consequences for health, livelihoods, and local
  resilience. Its 2025 Chabahar program targeted clean water and water-efficient
  agriculture for about 50,000 residents in five villages. ([UNDP Iran,
  2025-05-26](https://www.undp.org/iran/publications/undp-iran-chabahar-factsheet))
- In the Hamoun basin, UNDP reports that drought, degraded wetlands, dust and
  sand storms, and reduced water availability have damaged rural livelihoods
  based on agriculture, livestock, fishing, and handicrafts and contributed to
  displacement and poverty risk. ([UNDP Iran, project page accessed
  2026-08-26](https://www.undp.org/iran/projects/joint-project-between-doe-eu-and-undp-hamoun-area))
- UNICEF's account of the 2024 Dashtiyari floods documents blocked transport,
  interrupted water access, and sanitation problems in affected villages. This
  is a localized emergency account, not a description of every resident or
  business in the province. ([UNICEF Iran,
  2024-12-22](https://www.unicef.org/iran/en/stories/rebuilding-hope-unicefs-lifeline-irans-flood-stricken-communities))
- The most recent provincial labor figure located in this pass is older: a
  transparent secondary compilation of Statistical Centre of Iran data reports
  about **12% unemployment in Sistan and Baluchestan in 1402**, versus roughly
  8% nationally. It is useful only as evidence of a persistent provincial gap,
  not as a current 2026 rate. ([Iran Open Data, 2024-07-08](https://iranopendata.org/fa/article/201-which-provinces-have-the-highest-unemployment-rates/))

**Persona inference:** provincial scenarios need real variation. A Zahedan
retailer, a Chabahar service worker, an Iranshahr trader, and a rural producer
do not share one workflow. Weather, water, dust, road access, migration, and
seasonal work can change whether a promise or delivery is completed. The
persona must be locally grounded without being reduced to deprivation,
ethnicity, religion, or a rural stereotype.

### 3. Phone-first does not mean always connected

- ITU reports **127 active mobile-broadband subscriptions per 100 people in
  Iran in 2024**. A subscription count can exceed the population because a
  person or device may have multiple subscriptions; it is not a count of
  reliably connected people. ([ITU DataHub, 2024 data, accessed
  2026-08-26](https://datahub.itu.int/data/?c=&e=COD&i=11632&u=per+100+people&v=chart))
- ITU's latest displayed location split is from 2021: internet use was **65.7%
  in rural areas and 82.6% in urban areas**, while household internet access
  was **69.2% rural and 82.5% urban**. These are national, dated gaps—not
  Sistan-specific measurements—but they warn against assuming uniform access.
  ([ITU Iran Digital Development Dashboard, accessed
  2026-08-26](https://datahub.itu.int/data/?Connectivity=Emerging+technologies&Governance=Collaborative+regulation&Markets=Emerging+technologies+regulation&Sustainability=Society&e=IRN))
- Cloudflare observed two nationwide Iranian shutdowns in Q1 2026. During the
  shutdown beginning 2026-02-28, traffic fell to well under 1% of previous
  levels and Iran remained effectively offline through the end of that quarter.
  ([Cloudflare, 2026-04-30](https://blog.cloudflare.com/q1-2026-internet-disruption-summary/))

**Persona inference:** the character may be highly familiar with messaging and
voice notes while still encountering delay, weak connectivity, or sudden loss
of service. The product needs immediate receipts, idempotent retry, resumable
drafts, duplicate detection, short messages, and a complete plain-text path.
Silence or repeated delivery must never be interpreted as indecision or consent.

### 4. Informality is not the same as “people keep no records”

- ILO defines informal employment as a job-level concept involving work that
  commonly lacks social or legal protection; it can exist in formal firms,
  informal firms, or households. Informal-sector employment and informal
  employment are related but distinct measures. ([ILOSTAT concepts and
  definitions, accessed
  2026-08-26](https://ilostat.ilo.org/methods/concepts-and-definitions/description-labour-force-statistics/))
- ILO's Iran profile says its latest available household labor survey is the
  2024 Labour Force Survey, but this pass did not locate a trustworthy recent
  province-level measure of informal employment or routine business-recording
  behavior. ([ILOSTAT Iran profile, accessed
  2026-08-26](https://ilostat.ilo.org/data/country-profiles/irn/))

**Design boundary:** do not infer “no invoice,” “no written contract,” “cash
only,” or “cannot use software” from occupation, province, language, or
informality. Treat the owner's local observation as a recruitment question:

> When money, a promise, or a follow-up appears during work, where—if
> anywhere—does it get written down before the day ends?

Observe the answer and artifact. Do not ask only whether the participant “uses
accounting software.”

## Public-discussion signals: language only, not prevalence evidence

The following weak sources are useful only to make dialogue sound less
synthetic. They are self-selected, unaudited, and not representative of Iran or
Sistan and Baluchestan.

- A 2026 first-person Persian post about collecting a personal debt uses the
  language of avoidance and memory burden—“یادم رفت” and discomfort about
  asking—rather than accounting vocabulary. The page also promotes a product,
  so it must not be treated as independent demand validation. ([Virgool,
  2026-08](https://virgool.io/@m_21171647/sanado-tks58z4o6yik))
- A public merchant message says “کلی چک دارم” while describing the conflict
  between closing a shop and meeting obligations. It is from a political
  subreddit and dates to 2022, so only the compact obligation-centered phrasing
  is reusable. ([Reddit r/NewIran,
  2022-11-19](https://www.reddit.com/r/NewIran/comments/yz97g7))
- A 2026 reposted collection of accounts includes the terse image of shops being
  open but having no customers or income. It is translated/reposted political
  content, not verified ethnography. ([Reddit r/NewIran,
  2026-04-27](https://www.reddit.com/r/NewIran/comments/1swy3mv/from_inside_iran_part_79_your_accounts_of_the/))

**Dialogue implication:** realistic turns can be short, elliptical, and
relationship-centered—person first, then amount or obligation—with omitted
units, relative time, correction after the fact, and ordinary cancellation
language such as “بی‌خیال” or “ثبت نکن.” These are testable dialogue hypotheses,
not claims about how all Iranian users speak.

## Composite role to inhabit for the next design phase

Use a deliberately broad but coherent role:

> I am a locally rooted worker/operator in today's Sistan and Baluchestan. I am
> competent at my trade and responsible for money, promises, deliveries, and
> follow-ups, but I do not have a dependable external memory. My phone is the
> tool already in my hand. My records may be split across memory, calls,
> WhatsApp, bank SMS, paper, and occasional software. Prices and plans change
> quickly. I will use a new service only if it saves effort in the first few
> exchanges, does not shame me, explains what it stores, and lets me correct or
> cancel anything important.

While role-playing, the persona should:

- speak as a capable practitioner, not a product manager or a “low-literacy
  user” caricature;
- reveal only the information a busy person would naturally send first;
- sometimes omit unit, purpose, counterparty, due time, or whether a transfer
  was personal or business-related;
- use voice or fragmented text when hands and attention are occupied;
- expect one useful question at a time and abandon flows that feel like forms;
- care about reputation, repayment, and keeping promises without turning those
  values into branding slogans;
- worry about privacy, mistaken records, duplicate messages, and who can see a
  reminder;
- distinguish a practical tool from a friend, therapist, accountant, bank, or
  government system;
- change a prior answer when the real-world meaning becomes clear.

## What the 100 future scenarios must vary

This is a coverage frame, not a scenario set.

1. **Role:** employee, self-employed worker, retailer, tradesperson, office
   worker, transporter, producer, professional, family-business operator.
2. **Setting:** Zahedan, Chabahar/coast, northern Sistan/Hamoun, other town,
   village, road/mobile work.
3. **Record habit:** none, memory, paper, message search, bank SMS, spreadsheet,
   basic accounting app, mixed method.
4. **Economic event:** price change, partial payment, debt collection, returned
   goods, cancelled order, personal/business transfer, delayed wage, shortage.
5. **Infrastructure event:** weak signal, shutdown, power cut, duplicate send,
   delayed message, interrupted voice upload, device shared or unavailable.
6. **Conversation shape:** terse text, voice note, pasted SMS, typo, local term,
   omitted rial/toman, relative date, correction, joke, refusal, silence.
7. **Trust/privacy risk:** shared phone, lock-screen preview, sensitive
   counterparty, fear of formalization, unclear retention, deletion request.
8. **Success test:** less memory burden, correct confirmation, easy correction,
   later retrieval, no false sales claim, no duplicate, no unwanted reminder.

## Research gaps that require fieldwork before product commitment

- Actual recording artifacts used by 12–20 diverse participants across at
  least Zahedan, Chabahar, one northern-Sistan location, and one smaller
  town/rural setting.
- The real meaning and frequency of voice notes, bank-SMS copying, paper debt
  books, and WhatsApp search in work.
- Rial/toman conventions by context and the words people use for sales,
  receipts, debt, advance, wages, and inter-account transfers.
- Whether resistance to recording comes from effort, habit, trust, tax/formality
  concerns, shared-device privacy, literacy, tool cost, or lack of later value.
- Women's, young workers', employees', and family-business members' workflows;
  the owner/operator viewpoint alone is insufficient.
- What users consider a trustworthy receipt, acceptable raw-message retention,
  and a safe reminder preview.

Until these gaps are observed directly, scenario outputs should be marked
**research hypotheses**, not “Iranian user behavior.”
