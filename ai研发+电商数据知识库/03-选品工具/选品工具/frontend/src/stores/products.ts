import axios from 'axios'
import { defineStore } from 'pinia'

interface Product {
  id: string
  name: string
  price: number
  category: string
  platform: string
  sales: number
  rating: number
  trend: 'up' | 'down' | 'stable'
  createdAt: Date
}

interface ProductsState {
  products: Product[]
  loading: boolean
  total: number
  currentPage: number
  pageSize: number
}

export const useProductsStore = defineStore('products', {
  state: (): ProductsState => ({
    products: [],
    loading: false,
    total: 0,
    currentPage: 1,
    pageSize: 20
  }),

  getters: {
    getProductsByCategory: (state) => (category: string) => {
      return state.products.filter(p => p.category === category)
    },
    getTopProducts: (state) => {
      return [...state.products].sort((a, b) => b.sales - a.sales).slice(0, 10)
    }
  },

  actions: {
    async fetchProducts() {
      this.loading = true
      try {
        const { data } = await axios.get('/api/products', { params: { page: this.currentPage, pageSize: this.pageSize } }); this.products = data.items; this.total = data.total;
        this.loading = false
      } catch (error) {
        this.loading = false
      }
    },
    async addProduct(product: Omit<Product, 'id' | 'createdAt'>) {
      const { data } = await axios.post('/api/products', { ...product, status: 'watching', score: 0 }); this.products.unshift(data);
    },
    async updateProduct(id: string, dataToUpdate: Partial<Product>) {
      const { data } = await axios.put('/api/products/' + id, dataToUpdate); const idx = this.products.findIndex(p => p.id === id); if (idx >= 0) this.products[idx] = data;
    },
    async deleteProduct(id: string) {
      await axios.delete('/api/products/' + id); this.products = this.products.filter(p => p.id !== id);
    }
  }
})
