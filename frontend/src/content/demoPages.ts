/**
 * Content and structured metadata for the 5 public demo lecture pages.
 * Optimized for Search Engines (SEO), Answer Engines (AEO), and Generative Overviews (GEO).
 */

export interface DemoPageChapter {
  num: string
  title: string
  summary: string
}

export interface DemoPageTakeaway {
  term: string
  definition: string
}

export interface DemoPageQa {
  question: string
  answer: string
  source: string
}

export interface DemoPageData {
  slug: string
  lectureId: string
  path: string
  title: string
  metaTitle: string
  description: string
  institution: string
  category: string
  duration: string
  chapterCount: number
  badge: string
  headline: string
  answerSummary: string
  keyTakeaways: DemoPageTakeaway[]
  chapters: DemoPageChapter[]
  sampleQa: DemoPageQa[]
  faq: { q: string; a: string }[]
}

export const DEMO_PAGES: Record<string, DemoPageData> = {
  'algorithms-and-computation': {
    slug: 'algorithms-and-computation',
    lectureId: '8821152f-f6de-49e9-a885-0adaac6ba4cb',
    path: '/demo/algorithms-and-computation',
    title: 'Algorithms and Computation Study Guide',
    metaTitle: 'MIT 6.006: Algorithms and Computation — Lecture Notes, Quiz & AI Tutor',
    description:
      'Complete study pack for MIT 6.006 Lecture 1. Mathematical induction, correctness proofs, asymptotic running times, word-RAM model, and the birthday problem.',
    institution: 'MIT OpenCourseWare · 6.006',
    category: 'Computer Science & Algorithms',
    duration: '46 min',
    chapterCount: 9,
    badge: 'Algorithms',
    headline: 'Formal Problem Specifications, Correctness Proofs, and Asymptotic Efficiency',
    answerSummary:
      'This foundational MIT lecture establishes what an algorithm is and how computer scientists formally evaluate computational methods. A computational problem is defined as a binary relation mapping inputs to valid outputs. To prove correctness on arbitrarily large input sizes, mathematical induction is applied across base cases and inductive steps. Computational performance is modeled using the Word-RAM model with word size w >= lg(n), providing the theoretical foundation for asymptotic notation (O, Omega, Theta) using the birthday paradox as a concrete running example.',
    keyTakeaways: [
      {
        term: 'Computational Problem',
        definition:
          'A binary relation between an input space and an output space, verified through boolean predicate functions determining valid solutions.',
      },
      {
        term: 'Induction for Correctness',
        definition:
          'Proving an algorithm produces the correct output for all inputs by establishing a base case and demonstrating that correctness for input size k implies correctness for size k+1.',
      },
      {
        term: 'Word-RAM Architecture',
        definition:
          'A model of computation where memory consists of w-bit words capable of random access and basic arithmetic operations in O(1) constant time.',
      },
      {
        term: 'Asymptotic Analysis',
        definition:
          'Characterizing algorithmic scaling as input size n approaches infinity, bounding growth rates with Big-O (upper), Big-Omega (lower), and Big-Theta (tight).',
      },
      {
        term: 'The Birthday Paradox',
        definition:
          'A classic probability problem demonstrating how quadratic comparison sets (n choose 2) yield high collision probabilities with small sample sizes.',
      },
    ],
    chapters: [
      {
        num: '01',
        title: 'Course Introduction and Goals',
        summary: 'Overview of 6.006: solving problems, proving correctness, arguing efficiency, and communicating algorithms.',
      },
      {
        num: '02',
        title: 'Defining Computational Problems',
        summary: 'Formulating problems as binary relations between input and output spaces with correctness predicates.',
      },
      {
        num: '03',
        title: 'Generalizing Problems and Algorithms',
        summary: 'Handling arbitrarily sized inputs and establishing deterministic procedures as mathematical functions.',
      },
      {
        num: '04',
        title: 'Example: The Birthday Problem',
        summary: 'Specifying the duplicate birthday search and identifying pairwise collision patterns.',
      },
      {
        num: '05',
        title: 'Designing an Algorithm for the Birthday Problem',
        summary: 'Direct comparison pairs versus sorting methods to identify identical birthdays.',
      },
      {
        num: '06',
        title: 'Proving Algorithm Correctness',
        summary: 'Induction steps, invariant preservation, and edge cases in loop termination.',
      },
      {
        num: '07',
        title: 'Measuring Algorithm Efficiency',
        summary: 'Abstracting hardware speed through operation counting and asymptotic growth rates.',
      },
      {
        num: '08',
        title: 'The Word-RAM Model of Computation',
        summary: 'Constant-time word access, register widths, and memory addressing limits.',
      },
      {
        num: '09',
        title: 'Summary and Course Roadmap',
        summary: 'Connecting models of computation to data structures, search algorithms, and dynamic programming.',
      },
    ],
    sampleQa: [
      {
        question: 'What is the formal definition of a computational problem?',
        answer:
          'In the lecture, a computational problem is formally defined as a binary relation between an input space and an output space. It specifies which outputs are considered valid solutions for each input using predicate functions.',
        source: 'Ch 02 · 3:04',
      },
      {
        question: 'How does induction prove an algorithm\'s correctness?',
        answer:
          'Induction proves correctness across arbitrary inputs by establishing a base case for the smallest input size, then proving that correctness for input size k guarantees correctness for size k+1.',
        source: 'Ch 03 · 6:32',
      },
    ],
    faq: [
      {
        q: 'What prerequisites are needed for MIT 6.006?',
        a: 'Basic Python programming (MIT 6.0001) and discrete mathematics (proofs by induction, set theory, and logic from MIT 6.042J).',
      },
      {
        q: 'Why does MIT 6.006 use the Word-RAM model instead of counting clock cycles?',
        a: 'Clock cycles depend on hardware architecture, operating system scheduling, and compiler flags. The Word-RAM model provides a hardware-independent mathematical abstraction where constant-time word operations yield consistent asymptotic bounds.',
      },
      {
        q: 'Can I test my understanding of this lecture with quizzes and flashcards?',
        a: 'Yes. NorAI generates interactive 3-tier multiple choice quizzes, SM-2 spaced repetition flashcards, and an AI tutor grounded in this exact lecture.',
      },
    ],
  },

  'calculus-differentiation': {
    slug: 'calculus-differentiation',
    lectureId: '01b04840-fddb-4b31-a211-7bb28f189621',
    path: '/demo/calculus-differentiation',
    title: 'Introduction to Differentiation Study Guide',
    metaTitle: 'MIT 18.01: Differentiation & Limits — Lecture Notes, Quiz & AI Tutor',
    description:
      'Complete study pack for MIT 18.01 Single Variable Calculus Lecture 1. The derivative from first principles, limit definitions, secant to tangent slopes, and power rules.',
    institution: 'MIT OpenCourseWare · 18.01',
    category: 'Mathematics & Calculus',
    duration: '52 min',
    chapterCount: 8,
    badge: 'Calculus',
    headline: 'The Derivative from First Principles: Difference Quotients and Tangent Slopes',
    answerSummary:
      'This lecture by Professor David Jerison introduces differentiation from geometric and analytic first principles. Geometrically, the derivative is the instantaneous slope of a curve at a point, found by taking the limit of secant line slopes as the displacement delta x approaches zero. Analytically, the derivative is computed using the difference quotient [f(x + delta x) - f(x)] / delta x. The lecture works through the algebraic derivation for 1/x, establishes the power rule for integer and fractional exponents, and demonstrates optimization via rate-of-change applications.',
    keyTakeaways: [
      {
        term: 'Secant vs. Tangent Line',
        definition:
          'A secant line passes through two distinct points (x, f(x)) and (x + delta x, f(x + delta x)); as delta x approaches 0, the secant line rotates into the tangent line.',
      },
      {
        term: 'Limit Definition of Derivative',
        definition:
          'f\'(x) = lim(delta x -> 0) [f(x + delta x) - f(x)] / delta x, providing the instantaneous rate of change.',
      },
      {
        term: 'Differentiation of 1/x',
        definition:
          'Using common denominators and difference quotients, [1/(x + delta x) - 1/x]/delta x simplifies to -1/[x(x + delta x)], yielding -1/x^2 in the limit.',
      },
      {
        term: 'The Power Rule',
        definition:
          'For any real power r, d/dx(x^r) = r * x^(r-1), derived through binomial expansions and difference quotients.',
      },
      {
        term: 'Differentiability implies Continuity',
        definition:
          'A function must be continuous at a point to have a well-defined derivative, although continuity does not guarantee differentiability.',
      },
    ],
    chapters: [
      {
        num: '01',
        title: 'Geometric Interpretation of the Derivative',
        summary: 'Visualizing slopes of secant lines transitioning to tangent lines on smooth curves.',
      },
      {
        num: '02',
        title: 'Limit Definition of the Derivative',
        summary: 'Formulating the difference quotient [f(x0 + delta x) - f(x0)] / delta x and taking limits as delta x approaches 0.',
      },
      {
        num: '03',
        title: 'Differentiating 1/x and Power Functions',
        summary: 'Step-by-step algebraic evaluation of f(x) = 1/x resulting in f\'(x) = -1/x^2.',
      },
      {
        num: '04',
        title: 'General Power Rule for Integer Exponents',
        summary: 'Extending differentiation to polynomials using binomial expansion and induction.',
      },
      {
        num: '05',
        title: 'Continuity and Differentiability',
        summary: 'Why non-continuous functions fail to have derivatives, and sharp corners with discontinuous slopes.',
      },
      {
        num: '06',
        title: 'Physical Meaning: Rates of Change',
        summary: 'Connecting geometric slopes to instantaneous velocity and physical acceleration.',
      },
      {
        num: '07',
        title: 'Geometric Problem: Maximizing Area',
        summary: 'Applying derivatives to find stationary points and solve constrained optimization problems.',
      },
      {
        num: '08',
        title: 'Summary and Next Steps',
        summary: 'Previewing product rule, quotient rule, chain rule, and trigonometric differentiation.',
      },
    ],
    sampleQa: [
      {
        question: 'What is the limit definition of the derivative?',
        answer:
          'The derivative of f(x) at a point is the limit as delta x approaches zero of [f(x + delta x) - f(x)] / delta x, representing the instantaneous slope of the tangent line.',
        source: 'Ch 02 · 4:00',
      },
      {
        question: 'How do you differentiate 1/x from first principles?',
        answer:
          'Substitute into difference quotient: [1/(x + delta x) - 1/x] / delta x = -delta x / (delta x * x * (x + delta x)). Canceling delta x and letting delta x -> 0 gives -1/x^2.',
        source: 'Ch 03 · 8:00',
      },
    ],
    faq: [
      {
        q: 'What is the difference between an average rate of change and an instantaneous rate of change?',
        a: 'The average rate of change is measured over a finite interval between two points (secant slope), whereas the instantaneous rate of change is the derivative at a single exact instant (tangent slope).',
      },
      {
        q: 'Can every continuous function be differentiated?',
        a: 'No. Functions with sharp corners (like f(x) = |x| at x = 0) or vertical tangents are continuous but not differentiable at those points.',
      },
      {
        q: 'How does NorAI help me master calculus concepts?',
        a: 'NorAI gives you chapter-by-chapter mathematical notes with properly rendered LaTeX formulas, step-by-step derivation flashcards, and an AI tutor that points to the exact video timestamp of each proof.',
      },
    ],
  },

  'newtonian-mechanics': {
    slug: 'newtonian-mechanics',
    lectureId: 'c8cab2e7-52b7-4cdc-8386-f440d02f3f45',
    path: '/demo/newtonian-mechanics',
    title: 'Newtonian Mechanics Study Guide',
    metaTitle: 'Yale PHYS 200: Newtonian Mechanics — Lecture Notes, Quiz & AI Tutor',
    description:
      'Complete study pack for Yale PHYS 200 Lecture 1. Kinematics, position, velocity, acceleration, calculus connections, and systematic problem-solving methods.',
    institution: 'YaleCourses · PHYS 200',
    category: 'Physics & Mechanics',
    duration: '73 min',
    chapterCount: 10,
    badge: 'Mechanics',
    headline: 'Kinematics in One and Two Dimensions: Deriving Motion via Differential Calculus',
    answerSummary:
      'In this introductory lecture for Yale PHYS 200, Professor Ramamurti Shankar introduces the mathematical architecture of Newtonian mechanics. Motion in space is specified by position vectors x(t), whose first derivative with respect to time defines instantaneous velocity v(t) = dx/dt, and whose second derivative defines acceleration a(t) = dv/dt = d^2x/dt^2. The lecture derives kinematic equations for constant acceleration, illustrates numerical integration, sets up two-dimensional projectile motion, and demonstrates how to choose reference coordinate frames to simplify physical calculations.',
    keyTakeaways: [
      {
        term: 'Differential Kinematics',
        definition:
          'Velocity is the time rate of change of position v = dx/dt; acceleration is the time rate of change of velocity a = dv/dt.',
      },
      {
        term: 'Constant Acceleration Equations',
        definition:
          'When acceleration is uniform: v(t) = v0 + at, and x(t) = x0 + v0*t + 0.5*a*t^2.',
      },
      {
        term: 'Independence of Orthogonal Axes',
        definition:
          'In two-dimensional motion, orthogonal components (x and y) can be solved independently with time t acting as the common parameter.',
      },
      {
        term: 'Coordinate Invariance',
        definition:
          'Physical laws and vector relationships remain identical regardless of chosen origin or axis orientation, allowing strategic coordinate placement.',
      },
      {
        term: 'Systematic Mechanics Method',
        definition:
          'A four-step problem-solving sequence: identify known parameters, sketch physical configuration, choose coordinate directions, and integrate equations of motion.',
      },
    ],
    chapters: [
      {
        num: '01',
        title: 'Introduction to Physics and Mechanics',
        summary: 'The scope of classical mechanics and the reduction of natural phenomena to mathematical laws.',
      },
      {
        num: '02',
        title: 'Vectors and Coordinate Systems',
        summary: 'Defining reference frames, unit vectors, and vector decomposition in cartesian coordinates.',
      },
      {
        num: '03',
        title: 'Position, Displacement, and Trajectory',
        summary: 'Describing particle positions as continuous functions of time parameter t.',
      },
      {
        num: '04',
        title: 'Instantaneous Velocity via Calculus',
        summary: 'Computing velocity as the derivative limit of displacement over infinitesimal time intervals.',
      },
      {
        num: '05',
        title: 'Acceleration as the Rate of Change of Velocity',
        summary: 'Second-order derivatives, physical sensation of acceleration, and curved trajectories.',
      },
      {
        num: '06',
        title: 'Deriving the Constant-Acceleration Equations',
        summary: 'Integrating acceleration analytically from t = 0 to t to recover velocity and position formulas.',
      },
      {
        num: '07',
        title: 'Numerical Integration and Euler Method',
        summary: 'Discretizing motion into small time slices delta t to simulate arbitrary force profiles.',
      },
      {
        num: '08',
        title: 'Two-Dimensional Projectile Motion',
        summary: 'Combining constant horizontal velocity with constant downward gravitational acceleration.',
      },
      {
        num: '09',
        title: 'Common Misconceptions in Kinematics',
        summary: 'Distinguishing between zero velocity and zero acceleration at trajectory apex.',
      },
      {
        num: '10',
        title: 'Summary and Preview of Newton\'s Laws',
        summary: 'Transitioning from describing motion (kinematics) to explaining forces that cause motion (dynamics).',
      },
    ],
    sampleQa: [
      {
        question: 'What is the relationship between position, velocity, and acceleration?',
        answer:
          'Velocity is the first time derivative of position: v(t) = dx/dt. Acceleration is the first time derivative of velocity and the second time derivative of position: a(t) = dv/dt = d^2x/dt^2. Conversely, integrating acceleration over time yields velocity, and integrating velocity yields position.',
        source: 'Ch 04 · 12:40',
      },
      {
        question: 'What happens to velocity and acceleration at the apex of projectile motion?',
        answer:
          'At the peak of vertical trajectory, instantaneous vertical velocity vy is zero because it changes sign from positive to negative. However, acceleration ay remains non-zero and constant (-g = -9.8 m/s^2), continuously pulling downward.',
        source: 'Ch 08 · 48:15',
      },
    ],
    faq: [
      {
        q: 'Why is calculus required for Newtonian mechanics?',
        a: 'Forces and accelerations vary continuously in real physical systems. Differential calculus provides the language to define instantaneous rates of change, while integral calculus enables computing total displacement under variable acceleration.',
      },
      {
        q: 'What is the difference between distance traveled and displacement?',
        a: 'Displacement is a vector pointing from the initial position to the final position, while distance traveled is a scalar representing the total length of the path taken.',
      },
      {
        q: 'Can I study physics formulas with NorAI?',
        a: 'Yes. NorAI renders physics formulas in clean notation, generates practice problem sets with explanations, and connects every solution to Professor Shankar\'s blackboard derivation in the video.',
      },
    ],
  },

  'financial-markets': {
    slug: 'financial-markets',
    lectureId: '2e983ee0-ae41-4910-9239-099b34dee04c',
    path: '/demo/financial-markets',
    title: 'Finance and Insurance in the Modern Economy Study Guide',
    metaTitle: 'Yale ECON 252: Financial Markets — Lecture Notes, Quiz & AI Tutor',
    description:
      'Complete study pack for Yale ECON 252 Lecture 1. Risk pooling, insurance theory, Modern Portfolio Theory, debt vs. equity, behavioral finance, and banking crises.',
    institution: 'YaleCourses · ECON 252',
    category: 'Economics & Finance',
    duration: '74 min',
    chapterCount: 10,
    badge: 'Finance',
    headline: 'Risk Management, Insurance Principles, and Financial Institutions',
    answerSummary:
      'In this opening lecture for Yale ECON 252, Nobel Laureate Robert Shiller outlines why financial markets, insurance, and risk management systems are fundamental pillars of modern civilization. The lecture explores the mathematical mechanics of risk pooling under the law of large numbers, contrasting individual catastrophic risk with predictable aggregate group outcomes. Professor Shiller discusses the evolution of corporate finance (debt vs. equity), efficient market dynamics, behavioral anomalies that cause speculative bubbles, and systemic fragilities demonstrated in historical banking panics.',
    keyTakeaways: [
      {
        term: 'Risk Pooling',
        definition:
          'Combining independent risks across large populations so aggregate claims approach their expected mathematical value via the law of large numbers.',
      },
      {
        term: 'Moral Hazard',
        definition:
          'The tendency of insured parties to take greater risks or exercise less caution when they are protected from financial consequences.',
      },
      {
        term: 'Adverse Selection',
        definition:
          'Information asymmetry where individuals with higher unobservable risk profiles are disproportionately likely to purchase insurance.',
      },
      {
        term: 'Debt vs. Equity Financing',
        definition:
          'Debt represents fixed contractual obligations with liquidation priority, whereas equity represents residual ownership with variable returns and control rights.',
      },
      {
        term: 'Behavioral Finance',
        definition:
          'The study of financial markets incorporating psychological biases, herd behavior, and overconfidence that cause asset prices to deviate from efficient market values.',
      },
    ],
    chapters: [
      {
        num: '01',
        title: 'Introduction to Finance and Human Enterprise',
        summary: 'Why financial engineering coordinates large-scale human collaboration and allocates societal resources.',
      },
      {
        num: '02',
        title: 'Risk and the Law of Large Numbers',
        summary: 'Mathematical foundations of variance reduction through independent risk aggregation.',
      },
      {
        num: '03',
        title: 'Origins and Structure of Modern Insurance',
        summary: 'Historical development of maritime insurance, life annuities, and catastrophic loss underwriting.',
      },
      {
        num: '04',
        title: 'Adverse Selection and Moral Hazard',
        summary: 'Microeconomic market failures in insurance contracts and structural mitigation strategies (deductibles, co-pays).',
      },
      {
        num: '05',
        title: 'Corporate Finance: Equity and Limited Liability',
        summary: 'How limited liability corporations enable risk-taking and public capital aggregation.',
      },
      {
        num: '06',
        title: 'Fixed Income, Debt, and Bankruptcy',
        summary: 'Senior debt covenants, bond pricing mechanisms, and priority of claims in restructuring.',
      },
      {
        num: '07',
        title: 'Efficient Markets Hypothesis (EMH)',
        summary: 'The theory that market prices reflect all available information and follow random walks.',
      },
      {
        num: '08',
        title: 'Behavioral Anomalies and Speculative Bubbles',
        summary: 'Psychological drivers of asset mispricing, market irrationality, and historical crashes.',
      },
      {
        num: '09',
        title: 'Banking and Systemic Liquidity Risk',
        summary: 'Fractional reserve banking, maturity transformation, and bank runs.',
      },
      {
        num: '10',
        title: 'Democratizing Finance: Future Directions',
        summary: 'Expanding financial tools, inclusive insurance products, and social enterprise structures.',
      },
    ],
    sampleQa: [
      {
        question: 'Why does insurance rely on the law of large numbers?',
        answer:
          'Insurance pools independent risks across many individuals based on the law of large numbers. While any single individual faces catastrophic variance, the aggregate loss of a large group becomes highly predictable. Charging a premium slightly above expected payout allows risk-averse individuals to trade uncertain severe losses for a certain small cost.',
        source: 'Ch 02 · 14:10',
      },
      {
        question: 'What is the difference between moral hazard and adverse selection?',
        answer:
          'Adverse selection occurs before the contract is signed due to asymmetric information (higher-risk people buy more insurance). Moral hazard occurs after the contract is signed, where being insured changes behavior toward taking greater risks.',
        source: 'Ch 04 · 28:30',
      },
    ],
    faq: [
      {
        q: 'Why is insurance considered a financial market instrument?',
        a: 'Insurance is an economic contract that exchanges risk and contingent capital across time and states of the world, priced according to actuarial probability distributions and discount rates.',
      },
      {
        q: 'What role does Robert Shiller play in behavioral economics?',
        a: 'Robert Shiller was awarded the 2013 Nobel Prize in Economic Sciences for showing that asset prices are excessively volatile relative to fundamentals, establishing behavioral finance as a central field.',
      },
      {
        q: 'How does NorAI help economics students review?',
        a: 'NorAI synthesizes multi-hour financial lectures into concise chapter takeaways, definitions, and an AI tutor that can answer questions about market formulas and economic models.',
      },
    ],
  },

  'civil-war-reconstruction': {
    slug: 'civil-war-reconstruction',
    lectureId: '5f7225bf-ba41-46b9-aea9-da91c032b515',
    path: '/demo/civil-war-reconstruction',
    title: 'The Civil War and Reconstruction in American Memory Study Guide',
    metaTitle: 'Yale HIST 119: Civil War & Reconstruction — Lecture Notes, Quiz & AI Tutor',
    description:
      'Complete study pack for Yale HIST 119 Lecture 1 with Professor David Blight. Constitutional compromises, sectionalism, memory, and the unfinished revolution of Reconstruction.',
    institution: 'YaleCourses · HIST 119',
    category: 'History & Humanities',
    duration: '53 min',
    chapterCount: 10,
    badge: 'History',
    headline: 'Historical Memory, Constitutional Crisis, and the Legacy of Reconstruction',
    answerSummary:
      'In this introductory lecture for Yale HIST 119, Pulitzer Prize-winning historian David Blight examines how the Civil War and Reconstruction continue to define American democratic identity and historical memory. The lecture analyzes the founding constitutional consensus—including compromises like the Three-Fifths Clause and Fugitive Slave Clause—that embedded slavery into the nation\'s legal framework. Professor Blight discusses the clash between reconciliationist and emancipationist memories of the war, and argues why Reconstruction remains an "unfinished revolution" whose promises were rolled back with the end of federal enforcement in 1877.',
    keyTakeaways: [
      {
        term: 'Constitutional Compromises on Slavery',
        definition:
          'Structural accommodations in the 1787 Constitution (Three-Fifths Clause, 20-year slave trade moratorium, Fugitive Slave Clause) that protected slaveholder power without naming slavery.',
      },
      {
        term: 'Emancipationist Memory',
        definition:
          'The historical understanding of the Civil War as a moral crusade that destroyed chattel slavery and initiated racial equality and expanded civil rights.',
      },
      {
        term: 'Reconciliationist Memory',
        definition:
          'A post-war narrative that celebrated white soldierly valor on both sides while erasing slavery and African American civil rights from the national story.',
      },
      {
        term: 'The Reconstruction Amendments',
        definition:
          'The 13th (abolished slavery), 14th (birthright citizenship, equal protection, due process), and 15th (protected voting rights against racial discrimination) Amendments.',
      },
      {
        term: 'Unfinished Revolution',
        definition:
          'The historical assessment that although Reconstruction established revolutionary legal and political rights for freedpeople, the withdrawal of federal enforcement allowed white supremacy to re-impose disenfranchisement and segregation.',
      },
    ],
    chapters: [
      {
        num: '01',
        title: 'Introduction: Why the Civil War Never Goes Away',
        summary: 'How the Civil War functions as the theological and political vortex of American national identity.',
      },
      {
        num: '02',
        title: 'The Paradox of American Origins',
        summary: 'The contradiction between the rhetoric of universal liberty and the legal entrenchment of human chattel slavery.',
      },
      {
        num: '03',
        title: 'Constitutional Compromises of 1787',
        summary: 'Detailed examination of the Three-Fifths Clause, Fugitive Slave clause, and slave trade protections.',
      },
      {
        num: '04',
        title: 'Sectionalism and Western Expansion',
        summary: 'How territorial acquisition repeatedly ignited legislative crises over the extension of slavery.',
      },
      {
        num: '05',
        title: 'Ideological Divergence: North and South',
        summary: 'Contrasting the Northern free-labor ideology against the Southern positive-good defense of slavery.',
      },
      {
        num: '06',
        title: 'The Cataclysm of Secession and Total War',
        summary: 'The collapse of political compromises, Southern secession, and the mobilization of national resources.',
      },
      {
        num: '07',
        title: 'Emancipation as Military Necessity and Moral Awakening',
        summary: 'How wartime developments and self-emancipation forced Lincoln and Congress to issue the Emancipation Proclamation.',
      },
      {
        num: '08',
        title: 'Reconstruction: The Second American Founding',
        summary: 'Radical Reconstruction, black political leadership, and the creation of the 13th, 14th, and 15th Amendments.',
      },
      {
        num: '09',
        title: 'The Collapse of Reconstruction (1877)',
        summary: 'Northern fatigue, political compromise, and violent paramilitary suppression of black citizenship.',
      },
      {
        num: '10',
        title: 'Competing Memories and the Struggle Today',
        summary: 'The battle between reconciliationist myths and emancipationist truths in modern cultural memory.',
      },
    ],
    sampleQa: [
      {
        question: 'Why is Reconstruction described as an unfinished revolution?',
        answer:
          'Reconstruction is described as an unfinished revolution because although the 13th, 14th, and 15th Amendments abolished slavery, guaranteed birthright citizenship, and protected voting rights, the political withdrawal of federal enforcement after 1877 allowed Jim Crow segregation and racial disenfranchisement to reverse many democratic gains for nearly a century.',
        source: 'Ch 08 · 42:15',
      },
      {
        question: 'How did the 1787 Constitution address slavery without using the word "slave"?',
        answer:
          'The Framers deliberately avoided the word "slave," referring instead to "other persons" in the Three-Fifths Clause, "such persons as any of the States now existing shall think proper to admit" in the migration clause, and "person held to service or labour" in the Fugitive Slave Clause.',
        source: 'Ch 03 · 16:20',
      },
    ],
    faq: [
      {
        q: 'Who was Professor David Blight and what did he write?',
        a: 'David Blight is Sterling Professor of History at Yale University and author of the Pulitzer Prize-winning biography "Frederick Douglass: Prophet of Freedom" and "Race and Reunion: The Civil War in American Memory".',
      },
      {
        q: 'What were the primary goals of Radical Reconstruction?',
        a: 'Radical Republicans in Congress aimed to dismantle the plantation aristocracy, secure citizenship and voting rights for four million formerly enslaved African Americans, and build public education and legal infrastructure across the South.',
      },
      {
        q: 'How does NorAI help with history and humanities lectures?',
        a: 'NorAI organizes complex historical lectures into chronological chapters, tracks major historiographical arguments, and provides an AI tutor that quotes primary sources and lectures with exact video timestamps.',
      },
    ],
  },
}
