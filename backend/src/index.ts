import type { Core } from '@strapi/strapi';

const categories = [
  { name: 'Electronics', slug: 'electronics', description: 'Latest gadgets and electronic devices' },
  { name: 'Clothing', slug: 'clothing', description: 'Fashion for every style and occasion' },
  { name: 'Books', slug: 'books', description: 'Expand your knowledge and imagination' },
  { name: 'Home & Garden', slug: 'home-garden', description: 'Everything for your home and garden' },
  { name: 'Sports', slug: 'sports', description: 'Equipment and gear for active lifestyles' },
  { name: 'Toys', slug: 'toys', description: 'Fun and educational toys for all ages' },
];

const productsByCat: Record<string, Array<{
  name: string; slug: string; excerpt: string; price: number;
  comparePrice?: number; stock: number; sku: string; featured: boolean;
}>> = {
  electronics: [
    { name: 'Wireless Headphones Pro', slug: 'wireless-headphones-pro', excerpt: 'Premium noise-cancelling headphones with 30h battery life.', price: 149.99, comparePrice: 199.99, stock: 42, sku: 'EL-001', featured: true },
    { name: '4K Smart Monitor', slug: '4k-smart-monitor', excerpt: '27-inch 4K IPS display with USB-C connectivity.', price: 299.99, comparePrice: 349.99, stock: 18, sku: 'EL-002', featured: true },
    { name: 'Mechanical Keyboard', slug: 'mechanical-keyboard', excerpt: 'Tenkeyless mechanical keyboard with RGB backlight.', price: 89.99, stock: 65, sku: 'EL-003', featured: false },
    { name: 'USB-C Hub 7-in-1', slug: 'usb-c-hub-7-in-1', excerpt: 'Expand your laptop with HDMI, USB 3.0, SD card and more.', price: 49.99, stock: 120, sku: 'EL-004', featured: false },
  ],
  clothing: [
    { name: 'Classic White T-Shirt', slug: 'classic-white-t-shirt', excerpt: '100% organic cotton, relaxed fit, timeless design.', price: 29.99, stock: 200, sku: 'CL-001', featured: false },
    { name: 'Slim Fit Chinos', slug: 'slim-fit-chinos', excerpt: 'Comfortable stretch chinos for every occasion.', price: 59.99, comparePrice: 79.99, stock: 85, sku: 'CL-002', featured: true },
    { name: 'Leather Jacket', slug: 'leather-jacket', excerpt: 'Genuine leather biker jacket with quilted lining.', price: 189.99, stock: 25, sku: 'CL-003', featured: true },
    { name: 'Running Sneakers', slug: 'running-sneakers', excerpt: 'Lightweight responsive running shoes for daily training.', price: 99.99, comparePrice: 119.99, stock: 60, sku: 'CL-004', featured: false },
  ],
  books: [
    { name: 'The Art of Code', slug: 'the-art-of-code', excerpt: 'A journey through programming history and creativity.', price: 24.99, stock: 150, sku: 'BK-001', featured: false },
    { name: 'Design Thinking Guide', slug: 'design-thinking-guide', excerpt: 'Practical methods to solve complex problems creatively.', price: 19.99, stock: 90, sku: 'BK-002', featured: false },
    { name: 'Business Strategy 101', slug: 'business-strategy-101', excerpt: 'Essential frameworks for modern business leaders.', price: 22.99, stock: 75, sku: 'BK-003', featured: false },
    { name: 'Python for Everyone', slug: 'python-for-everyone', excerpt: 'Learn Python programming from scratch with real projects.', price: 34.99, comparePrice: 44.99, stock: 200, sku: 'BK-004', featured: false },
  ],
  'home-garden': [
    { name: 'Bamboo Cutting Board Set', slug: 'bamboo-cutting-board-set', excerpt: 'Set of 3 sustainable bamboo cutting boards.', price: 39.99, stock: 80, sku: 'HG-001', featured: false },
    { name: 'Ceramic Plant Pot Set', slug: 'ceramic-plant-pot-set', excerpt: 'Minimalist glazed ceramic pots with drainage holes.', price: 44.99, stock: 55, sku: 'HG-002', featured: false },
    { name: 'LED Desk Lamp', slug: 'led-desk-lamp', excerpt: 'Eye-care LED lamp with wireless charging base.', price: 54.99, comparePrice: 69.99, stock: 40, sku: 'HG-003', featured: false },
    { name: 'Scented Candle Gift Set', slug: 'scented-candle-gift-set', excerpt: 'Set of 4 soy wax candles in seasonal fragrances.', price: 34.99, stock: 100, sku: 'HG-004', featured: false },
  ],
  sports: [
    { name: 'Yoga Mat Premium', slug: 'yoga-mat-premium', excerpt: 'Extra thick non-slip yoga mat with carrying strap.', price: 49.99, comparePrice: 64.99, stock: 70, sku: 'SP-001', featured: false },
    { name: 'Resistance Band Set', slug: 'resistance-band-set', excerpt: 'Set of 5 resistance bands for full-body training.', price: 24.99, stock: 150, sku: 'SP-002', featured: false },
    { name: 'Insulated Water Bottle 1L', slug: 'insulated-water-bottle-1l', excerpt: 'Keeps drinks cold 24h or hot 12h, BPA-free stainless steel.', price: 34.99, stock: 200, sku: 'SP-003', featured: false },
    { name: 'Speed Jump Rope', slug: 'speed-jump-rope', excerpt: 'Adjustable speed rope with ball bearings for smooth rotation.', price: 19.99, stock: 120, sku: 'SP-004', featured: false },
  ],
  toys: [
    { name: 'Building Blocks Set 500pc', slug: 'building-blocks-500pc', excerpt: 'Creative building blocks compatible with major brands.', price: 44.99, comparePrice: 54.99, stock: 60, sku: 'TY-001', featured: false },
    { name: 'Remote Control Car', slug: 'remote-control-car', excerpt: '1:16 scale off-road RC car with 30min battery life.', price: 59.99, stock: 35, sku: 'TY-002', featured: false },
    { name: 'Wooden Train Set', slug: 'wooden-train-set', excerpt: '50-piece wooden train set with magnetic connections.', price: 64.99, stock: 45, sku: 'TY-003', featured: false },
    { name: 'Puzzle 1000 Pieces', slug: 'puzzle-1000-pieces', excerpt: 'Scenic mountain landscape puzzle for ages 12+.', price: 22.99, stock: 90, sku: 'TY-004', featured: false },
  ],
};

const tags = [
  { name: 'Technology', slug: 'technology' },
  { name: 'Travel', slug: 'travel' },
  { name: 'Lifestyle', slug: 'lifestyle' },
  { name: 'Food', slug: 'food' },
  { name: 'Design', slug: 'design' },
  { name: 'Business', slug: 'business' },
  { name: 'Health', slug: 'health' },
  { name: 'Culture', slug: 'culture' },
];

const articles = [
  {
    title: 'The Future of Wireless Audio',
    slug: 'future-of-wireless-audio',
    excerpt: 'How Bluetooth 5.3 and lossless codecs are revolutionizing the way we listen to music.',
    tagSlugs: ['technology'],
    content: [
      { type: 'paragraph', children: [{ type: 'text', text: 'The audio industry has seen tremendous innovation over the past decade. With the advent of Bluetooth 5.3 and advanced codecs like aptX Lossless, wireless audio has finally closed the gap with wired connections.' }] },
      { type: 'heading', level: 2, children: [{ type: 'text', text: 'What Makes Modern Headphones Special' }] },
      { type: 'paragraph', children: [{ type: 'text', text: 'Modern wireless headphones combine active noise cancellation, spatial audio processing, and AI-driven sound tuning to deliver a personalized listening experience that adapts to your environment.' }] },
    ],
  },
  {
    title: '10 Must-Visit Cities in 2025',
    slug: '10-must-visit-cities-2025',
    excerpt: 'From hidden gems in Southeast Asia to revitalized European capitals, here are the top destinations this year.',
    tagSlugs: ['travel', 'culture'],
    content: [
      { type: 'paragraph', children: [{ type: 'text', text: 'Travel has rebounded strongly, and 2025 promises some incredible destinations for adventurous travelers. Whether you are looking for culture, cuisine, or natural beauty, these cities have it all.' }] },
      { type: 'heading', level: 2, children: [{ type: 'text', text: 'Porto, Portugal' }] },
      { type: 'paragraph', children: [{ type: 'text', text: 'Porto continues to enchant visitors with its tiled facades, world-class wine, and vibrant arts scene.' }] },
    ],
  },
  {
    title: 'Building a Morning Routine That Sticks',
    slug: 'building-morning-routine-that-sticks',
    excerpt: 'Science-backed strategies to design a morning routine that boosts productivity and mental clarity.',
    tagSlugs: ['health', 'lifestyle'],
    content: [
      { type: 'paragraph', children: [{ type: 'text', text: 'The morning sets the tone for the entire day. Research consistently shows that people with structured morning routines report higher levels of focus, lower stress, and greater life satisfaction.' }] },
      { type: 'heading', level: 2, children: [{ type: 'text', text: 'Start Small' }] },
      { type: 'paragraph', children: [{ type: 'text', text: 'The biggest mistake people make is trying to overhaul their entire morning at once. Start with just one habit and build from there.' }] },
    ],
  },
  {
    title: 'Farm-to-Table: The Restaurant Revolution',
    slug: 'farm-to-table-restaurant-revolution',
    excerpt: 'How local sourcing is reshaping menus and customer expectations in fine dining and beyond.',
    tagSlugs: ['food', 'lifestyle'],
    content: [
      { type: 'paragraph', children: [{ type: 'text', text: 'The farm-to-table movement has evolved from a niche trend into a mainstream philosophy reshaping how restaurants source ingredients and how diners think about their meals.' }] },
    ],
  },
  {
    title: 'Minimalism in Product Design',
    slug: 'minimalism-in-product-design',
    excerpt: 'Why less is more when it comes to creating products that stand the test of time.',
    tagSlugs: ['design', 'technology'],
    content: [
      { type: 'paragraph', children: [{ type: 'text', text: 'Dieter Rams famously defined good design with ten principles, chief among them: good design is as little design as possible. Decades later, this philosophy remains the gold standard for product designers worldwide.' }] },
      { type: 'heading', level: 2, children: [{ type: 'text', text: 'Removing the Unnecessary' }] },
      { type: 'paragraph', children: [{ type: 'text', text: 'Minimalist design is about ruthlessly prioritizing what matters. Every element should serve a purpose, and if it does not, it should be removed.' }] },
    ],
  },
  {
    title: 'Remote Work Is Here to Stay',
    slug: 'remote-work-is-here-to-stay',
    excerpt: 'The data on remote work adoption, productivity, and what it means for the future of offices.',
    tagSlugs: ['business', 'lifestyle'],
    content: [
      { type: 'paragraph', children: [{ type: 'text', text: 'Five years after the pandemic forced a global experiment in remote work, the results are in: distributed teams can be just as productive as their in-office counterparts.' }] },
    ],
  },
  {
    title: 'The Science of Better Sleep',
    slug: 'science-of-better-sleep',
    excerpt: 'What chronobiology and sleep research tell us about optimizing rest for performance and longevity.',
    tagSlugs: ['health'],
    content: [
      { type: 'paragraph', children: [{ type: 'text', text: 'Sleep is an active biological process that consolidates memories, repairs tissues, regulates hormones, and clears metabolic waste from the brain.' }] },
    ],
  },
  {
    title: 'AI Tools Transforming Small Business',
    slug: 'ai-tools-transforming-small-business',
    excerpt: 'How entrepreneurs are using AI for marketing, customer service, and operations without breaking the bank.',
    tagSlugs: ['business', 'technology'],
    content: [
      { type: 'paragraph', children: [{ type: 'text', text: 'Artificial intelligence is no longer the exclusive domain of large enterprises. Today, small business owners use AI-powered tools to compete with bigger players.' }] },
    ],
  },
  {
    title: 'Street Food Around the World',
    slug: 'street-food-around-the-world',
    excerpt: 'A culinary journey through the most iconic street food dishes from Bangkok to Mexico City.',
    tagSlugs: ['food', 'travel', 'culture'],
    content: [
      { type: 'paragraph', children: [{ type: 'text', text: 'Street food is the most honest form of a cuisine shaped by local ingredients, history, and culture. From Bangkok pad thai to Mexico City tacos, street food tells the story of a place better than any restaurant.' }] },
    ],
  },
  {
    title: 'Color Theory for Non-Designers',
    slug: 'color-theory-for-non-designers',
    excerpt: 'Understanding the basics of color psychology and how to apply it to your brand and products.',
    tagSlugs: ['design'],
    content: [
      { type: 'paragraph', children: [{ type: 'text', text: 'You do not need a design degree to make better color choices. A basic understanding of color theory can dramatically improve everything from your marketing materials to your home decor.' }] },
    ],
  },
  {
    title: 'Sustainable Shopping Guide',
    slug: 'sustainable-shopping-guide',
    excerpt: 'How to make more conscious purchasing decisions without sacrificing quality or style.',
    tagSlugs: ['lifestyle', 'culture'],
    content: [
      { type: 'paragraph', children: [{ type: 'text', text: 'Sustainable shopping means being more intentional about what you buy, from whom, and why. Small changes in purchasing behavior, multiplied across millions of consumers, can have a meaningful impact.' }] },
    ],
  },
  {
    title: 'The Rise of the Creator Economy',
    slug: 'rise-of-creator-economy',
    excerpt: 'Why 50 million people now consider themselves creators and what this means for business and culture.',
    tagSlugs: ['business', 'culture', 'technology'],
    content: [
      { type: 'paragraph', children: [{ type: 'text', text: 'The creator economy has grown exponentially. An estimated 50 million people worldwide now identify as creators earning a living through their content.' }] },
    ],
  },
];

async function seedData(strapi: Core.Strapi) {
  strapi.log.info('[seed] Starting data seed...');

  const catMap: Record<string, string> = {};
  for (const cat of categories) {
    const created = await strapi.documents('api::category.category').create({ data: cat });
    catMap[cat.slug] = created.documentId;
    strapi.log.info(`[seed] Created category: ${cat.name}`);
  }

  for (const [catSlug, products] of Object.entries(productsByCat)) {
    for (const product of products) {
      await strapi.documents('api::product.product').create({
        data: {
          ...product,
          description: `## ${product.name}\n\n${product.excerpt}\n\nThis product is crafted with care and attention to detail. Whether you are looking for everyday use or a special occasion, this item delivers exceptional value and quality.\n\n### Features\n- Premium materials\n- Satisfaction guaranteed\n- Fast shipping`,
          category: catMap[catSlug],
        },
        status: 'published',
      });
      strapi.log.info(`[seed] Created product: ${product.name}`);
    }
  }

  const tagMap: Record<string, string> = {};
  for (const tag of tags) {
    const created = await strapi.documents('api::tag.tag').create({ data: tag });
    tagMap[tag.slug] = created.documentId;
    strapi.log.info(`[seed] Created tag: ${tag.name}`);
  }

  for (const article of articles) {
    const tagDocIds = article.tagSlugs
      .filter((s) => tagMap[s])
      .map((s) => tagMap[s]);

    await strapi.documents('api::article.article').create({
      data: {
        title: article.title,
        slug: article.slug,
        excerpt: article.excerpt,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        content: article.content as any,
        tags: tagDocIds,
      },
      status: 'published',
    });
    strapi.log.info(`[seed] Created article: ${article.title}`);
  }

  strapi.log.info('[seed] Seed complete!');
}

export default {
  register() {},

  async bootstrap({ strapi }: { strapi: Core.Strapi }) {
    const count = await strapi.documents('api::product.product').count({});
    if (count === 0) {
      await seedData(strapi);
    }
  },
};
