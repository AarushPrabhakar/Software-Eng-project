import { Backpack, CupSoda, Wallet, Headphones, KeyRound, BookOpen, Package } from 'lucide-react'
import { CATEGORY_VALUE } from '../data/mockItems.js'

const ICONS = {
  backpacks_bags: Backpack,
  water_bottles: CupSoda,
  wallets_purses: Wallet,
  earbuds_headphones: Headphones,
  keys_keychains: KeyRound,
  books_notebooks: BookOpen,
}

// accepts either the display label ("Wallets & purses") or the enum value ("wallets_purses")
export default function CategoryIcon({ category, size = 22, strokeWidth = 2 }) {
  const Icon = ICONS[CATEGORY_VALUE[category] || category] || Package
  return <Icon size={size} strokeWidth={strokeWidth} aria-hidden="true" />
}
