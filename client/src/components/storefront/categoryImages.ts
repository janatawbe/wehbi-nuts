import coffee from '../../assets/category_images/coffee.png'
import driedFruits from '../../assets/category_images/dried_fruits.png'
import nuts from '../../assets/category_images/nuts.png'
import snacksSweets from '../../assets/category_images/snacks_and_sweets.png'
import seeds from '../../assets/category_images/seeds.png'
import spiceHerbs from '../../assets/category_images/spice_and_herbs.png'
import gifts from '../../assets/category_images/gifts.png'

/** Real product photography for each of the seven official categories,
 * shot on a soft cream backdrop that already blends into the page.
 * Shared by every place a category needs a thumbnail -- CategoryTile
 * (homepage) and the Shop page's compact category rail -- so there is
 * exactly one place mapping a category slug to its image. */
export const CATEGORY_IMAGES: Record<string, string> = {
  coffee,
  'dried-fruits': driedFruits,
  nuts,
  'snacks-sweets': snacksSweets,
  seeds,
  'spice-herbs': spiceHerbs,
  gifts,
}
