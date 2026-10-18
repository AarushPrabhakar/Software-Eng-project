// Display labels shown in the UI (unchanged from the original design).
export const CATEGORIES = [
  'Backpacks & bags',
  'Water bottles & tumblers',
  'Wallets & purses',
  'Earbuds & headphone cases',
  'Keys & keychains',
  'Books & notebooks',
]

// Maps each display label to the enum value the backend/database expects.
export const CATEGORY_VALUE = {
  'Backpacks & bags': 'backpacks_bags',
  'Water bottles & tumblers': 'water_bottles',
  'Wallets & purses': 'wallets_purses',
  'Earbuds & headphone cases': 'earbuds_headphones',
  'Keys & keychains': 'keys_keychains',
  'Books & notebooks': 'books_notebooks',
}

// Reverse lookup: backend enum value -> display label.
export const CATEGORY_LABEL = Object.fromEntries(
  Object.entries(CATEGORY_VALUE).map(([label, value]) => [value, label])
)

export const LOCATIONS = [
  'LT Complex',
  'Central Library',
  'Hostel J',
  'Hostel A',
  'Sports Complex',
  'Cafeteria',
  'Academic Block 2',
]

/**
 * Converts a raw report row from the backend (snake_case, enum category,
 * event_date) into the shape the existing UI components (TagCard,
 * ItemDetail, Feed) already expect (id, type, category label, date, etc).
 */
export function toViewItem(report) {
  return {
    id: report.report_code,
    reportId: report.id,
    type: report.report_type,
    status: report.status,
    category: CATEGORY_LABEL[report.category] || report.category,
    title: report.title,
    description: report.public_description || '',
    brand: report.brand || '—',
    colour: report.colour || '—',
    location: report.campus_location || '—',
    date: report.event_date || null,
    imageUrl: report.image_url || null,
    // found items are shown as "title only" until your own lost report matches them
    redacted: !!report.redacted,
    access: report.access || 'public',
    matchScore: report.match_score || null,
  }
}
