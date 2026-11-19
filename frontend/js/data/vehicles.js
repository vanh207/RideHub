(function (global) {
  'use strict';

  const VEHICLES = [
    { id: 'v1', name: 'VinFast Feliz S (2025)', type: 'moto', category: 'Xe máy', transmission: 'Số tự động', fuel: 'Điện', seats: '2 chỗ', price: 160000, rating: '4.9', trips: '142 chuyến', address: '45 Lý Tự Trọng, Quận 1, TP.HCM', ownerKey: 'moto' },
    { id: 'v2', name: 'Honda Vision Smartkey (2024)', type: 'moto', category: 'Xe máy', transmission: 'Số tự động', fuel: 'Xăng', seats: '2 chỗ', price: 140000, rating: '4.8', trips: '215 chuyến', address: '72 CMT8, Quận 3, TP.HCM', ownerKey: 'moto' },
    { id: 'v3', name: 'VinFast Evo200 Lite (2025)', type: 'moto', category: 'Xe máy', transmission: 'Số tự động', fuel: 'Điện', seats: '2 chỗ', price: 130000, rating: '4.9', trips: '98 chuyến', address: '120 Nguyễn Huệ, Quận 1, TP.HCM', ownerKey: 'moto' },
    { id: 'v4', name: 'Dat Bike Weaver++ (2024)', type: 'moto', category: 'Xe máy', transmission: 'Xe côn tay', fuel: 'Điện', seats: '2 chỗ', price: 220000, rating: '4.9', trips: '87 chuyến', address: '18 Nguyễn Thị Minh Khai, Q.1, TP.HCM', ownerKey: 'moto' },
    { id: 'v5', name: 'Yamaha Grande Hybrid (2024)', type: 'moto', category: 'Xe máy', transmission: 'Số tự động', fuel: 'Xăng/Điện', seats: '2 chỗ', price: 170000, rating: '4.8', trips: '120 chuyến', address: '55 Hai Bà Trưng, Quận 1, TP.HCM', ownerKey: 'moto' },
    { id: 'v6', name: 'Honda Air Blade 160 (2025)', type: 'moto', category: 'Xe máy', transmission: 'Số tự động', fuel: 'Xăng', seats: '2 chỗ', price: 180000, rating: '4.9', trips: '164 chuyến', address: '102 Trần Hưng Đạo, Quận 5, TP.HCM', ownerKey: 'moto' },
    { id: 'v7', name: 'VinFast Klara S (2024)', type: 'moto', category: 'Xe máy', transmission: 'Số tự động', fuel: 'Điện', seats: '2 chỗ', price: 150000, rating: '4.7', trips: '76 chuyến', address: '34 Lê Duẩn, Quận 1, TP.HCM', ownerKey: 'moto' },
    { id: 'v8', name: 'Honda Wave Alpha (2024)', type: 'moto', category: 'Xe máy', transmission: 'Xe số', fuel: 'Xăng', seats: '2 chỗ', price: 100000, rating: '4.7', trips: '310 chuyến', address: '90 Hoàng Văn Thụ, Tân Bình, TP.HCM', ownerKey: 'moto' },
    { id: 'v9', name: 'Yamaha Exciter 155 VVA', type: 'moto', category: 'Xe máy', transmission: 'Xe côn tay', fuel: 'Xăng', seats: '2 chỗ', price: 190000, rating: '4.8', trips: '135 chuyến', address: '205 Điện Biên Phủ, Bình Thạnh, TP.HCM', ownerKey: 'moto' },
    { id: 'v10', name: 'VinFast Vento S (2025)', type: 'moto', category: 'Xe máy', transmission: 'Số tự động', fuel: 'Điện', seats: '2 chỗ', price: 210000, rating: '4.9', trips: '62 chuyến', address: '45 Lý Tự Trọng, Quận 1, TP.HCM', ownerKey: 'moto' },
    { id: 'v11', name: 'Honda SH Mode 125 (2024)', type: 'moto', category: 'Xe máy', transmission: 'Số tự động', fuel: 'Xăng', seats: '2 chỗ', price: 240000, rating: '4.9', trips: '188 chuyến', address: '12 Nguyễn Trãi, Quận 1, TP.HCM', ownerKey: 'moto' },
    { id: 'v12', name: 'Yamaha Sirius Fi (2024)', type: 'moto', category: 'Xe máy', transmission: 'Xe số', fuel: 'Xăng', seats: '2 chỗ', price: 110000, rating: '4.7', trips: '145 chuyến', address: '88 Quang Trung, Gò Vấp, TP.HCM', ownerKey: 'moto' },
    { id: 'v13', name: 'VinFast VF 5 Plus (2025)', type: 'car', category: 'Ô tô', transmission: 'Số tự động', fuel: 'Điện', seats: '5 chỗ', price: 750000, rating: '4.9', trips: '154 chuyến', address: '240 Võ Văn Ngân, Thủ Đức, TP.HCM', ownerKey: 'car' },
    { id: 'v14', name: 'Mazda 3 Luxury Sedan (2024)', type: 'car', category: 'Ô tô', transmission: 'Số tự động', fuel: 'Xăng', seats: '5 chỗ', price: 850000, rating: '4.9', trips: '112 chuyến', address: '12 Tôn Đức Thắng, Quận 1, TP.HCM', ownerKey: 'car' },
    { id: 'v15', name: 'VinFast VF e34 (2024)', type: 'car', category: 'Ô tô', transmission: 'Số tự động', fuel: 'Điện', seats: '5 chỗ', price: 800000, rating: '4.8', trips: '95 chuyến', address: '68 Mai Chí Thọ, TP. Thủ Đức, TP.HCM', ownerKey: 'car' },
    { id: 'v16', name: 'Toyota Fortuner Legender (2024)', type: 'car', category: 'Ô tô', transmission: 'Số tự động', fuel: 'Dầu', seats: '7 chỗ', price: 1250000, rating: '4.9', trips: '88 chuyến', address: '240 Võ Văn Ngân, Thủ Đức, TP.HCM', ownerKey: 'car' },
    { id: 'v17', name: 'Hyundai Accent AT (2024)', type: 'car', category: 'Ô tô', transmission: 'Số tự động', fuel: 'Xăng', seats: '5 chỗ', price: 650000, rating: '4.7', trips: '190 chuyến', address: '350 Cộng Hòa, Tân Bình, TP.HCM', ownerKey: 'car' },
    { id: 'v18', name: 'Kia Carnival Signature (2024)', type: 'car', category: 'Ô tô', transmission: 'Số tự động', fuel: 'Dầu', seats: '7 chỗ', price: 1650000, rating: '5.0', trips: '72 chuyến', address: '15 Lê Duẩn, Quận 1, TP.HCM', ownerKey: 'car' },
    { id: 'v19', name: 'VinFast VF 8 Plus (2025)', type: 'car', category: 'Ô tô', transmission: 'Số tự động', fuel: 'Điện', seats: '5 chỗ', price: 1150000, rating: '4.9', trips: '104 chuyến', address: 'Landmark 81, Bình Thạnh, TP.HCM', ownerKey: 'car' },
    { id: 'v20', name: 'Honda City RS (2024)', type: 'car', category: 'Ô tô', transmission: 'Số tự động', fuel: 'Xăng', seats: '5 chỗ', price: 700000, rating: '4.8', trips: '140 chuyến', address: '180 Phan Đăng Lưu, Phú Nhuận, TP.HCM', ownerKey: 'car' },
    { id: 'v21', name: 'Mitsubishi Xpander Premium (2024)', type: 'car', category: 'Ô tô', transmission: 'Số tự động', fuel: 'Xăng', seats: '7 chỗ', price: 850000, rating: '4.8', trips: '220 chuyến', address: '42 Nguyễn Thị Thập, Quận 7, TP.HCM', ownerKey: 'car' },
    { id: 'v22', name: 'VinFast VF 6 Plus (2025)', type: 'car', category: 'Ô tô', transmission: 'Số tự động', fuel: 'Điện', seats: '5 chỗ', price: 890000, rating: '4.9', trips: '83 chuyến', address: '240 Võ Văn Ngân, Thủ Đức, TP.HCM', ownerKey: 'car' },
    { id: 'v23', name: 'Toyota Corolla Cross Hybrid', type: 'car', category: 'Ô tô', transmission: 'Số tự động', fuel: 'Xăng/Điện', seats: '5 chỗ', price: 950000, rating: '4.9', trips: '115 chuyến', address: '50 Bến Vân Đồn, Quận 4, TP.HCM', ownerKey: 'car' },
    { id: 'v24', name: 'VinFast VF 9 Plus (2025)', type: 'car', category: 'Ô tô', transmission: 'Số tự động', fuel: 'Điện', seats: '7 chỗ', price: 1850000, rating: '5.0', trips: '46 chuyến', address: '45 Lý Tự Trọng, Quận 1, TP.HCM', ownerKey: 'car' }
  ];

  const OWNERS = {
    moto: {
      initials: 'GR',
      name: 'GreenRide Quận 1 (Anh Lê Hoàng Nam)',
      rating: '4.9',
      trips: '337 chuyến',
      response: 'Phản hồi 99% trong 5 phút',
      addr: '45 Lý Tự Trọng, Quận 1, TP.HCM',
      fleetIds: ['v1', 'v2', 'v3']
    },
    car: {
      initials: 'ED',
      name: 'EcoDrive Thủ Đức (Chị Nguyễn Thu Thảo)',
      rating: '4.8',
      trips: '150 chuyến',
      response: 'Phản hồi 98% trong 10 phút',
      addr: '240 Võ Văn Ngân, Thủ Đức, TP.HCM',
      fleetIds: ['v13', 'v16', 'v14']
    }
  };

  const FAVORITES_KEY = 'ridehub_favorite_vehicles';

  function formatCurrency(value) {
    return Number(value).toLocaleString('vi-VN') + 'đ';
  }

  function getVehicleById(id) {
    return VEHICLES.find((vehicle) => vehicle.id === id) || null;
  }

  function getOwnerForVehicle(vehicle) {
    return OWNERS[vehicle && vehicle.ownerKey] || OWNERS.moto;
  }

  function getOwnerFleet(owner) {
    return (owner.fleetIds || []).map(getVehicleById).filter(Boolean);
  }

  function getFavorites() {
    try {
      const raw = localStorage.getItem(FAVORITES_KEY);
      const list = raw ? JSON.parse(raw) : [];
      return Array.isArray(list) ? list : [];
    } catch (_) {
      return [];
    }
  }

  function saveFavorites(list) {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(list));
  }

  function isFavorite(vehicle) {
    return getFavorites().some((item) => item.id === vehicle.id || item.name === vehicle.name);
  }

  function toggleFavorite(vehicle) {
    let list = getFavorites();
    const exists = list.some((item) => item.id === vehicle.id || item.name === vehicle.name);
    if (exists) {
      list = list.filter((item) => item.id !== vehicle.id && item.name !== vehicle.name);
      saveFavorites(list);
      return false;
    }
    list.push({
      id: vehicle.id,
      name: vehicle.name,
      specs: `${vehicle.transmission} • ${vehicle.fuel} • ${vehicle.seats}`,
      address: vehicle.address,
      price: formatCurrency(vehicle.price) + '/ngày',
      svg: getVehicleSvg(vehicle)
    });
    saveFavorites(list);
    return true;
  }

  function getVehicleSvg(vehicle) {
    if (vehicle.type === 'car') {
      return `<svg viewBox="0 0 180 96" width="100%" height="110" fill="none"><rect width="180" height="96" rx="12" fill="#ecfdf5"/><circle cx="50" cy="68" r="14" fill="#14532d"/><circle cx="50" cy="68" r="7" fill="#bbf7d0"/><circle cx="130" cy="68" r="14" fill="#14532d"/><circle cx="130" cy="68" r="7" fill="#bbf7d0"/><path d="M28 66c0-12 8-22 20-24l22-18h50l24 16c14 4 20 14 20 26H28z" fill="#22c55e" opacity="0.85" stroke="#15803d" stroke-width="2.5"/><path d="M68 26l-14 16h40V26H68zm30 0v16h34l-14-16H98z" fill="#f0fdf4" stroke="#15803d" stroke-width="1.5"/></svg>`;
    }
    return `<svg viewBox="0 0 180 96" width="100%" height="110" fill="none"><rect width="180" height="96" rx="12" fill="#f0fdf4"/><circle cx="48" cy="68" r="14" fill="#14532d"/><circle cx="48" cy="68" r="6" fill="#bbf7d0"/><circle cx="132" cy="68" r="14" fill="#14532d"/><circle cx="132" cy="68" r="6" fill="#bbf7d0"/><path d="M48 68c0-8 6-16 16-16h24l16-24h20l-12 24h18" stroke="#15803d" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><path d="M76 52l12-20h22" stroke="#22c55e" stroke-width="3.5" stroke-linecap="round"/><path d="M78 48c10-14 26-14 36 0" fill="#22c55e" opacity="0.6"/></svg>`;
  }

  global.RideHubData = {
    VEHICLES,
    OWNERS,
    FAVORITES_KEY,
    formatCurrency,
    getVehicleById,
    getOwnerForVehicle,
    getOwnerFleet,
    getFavorites,
    saveFavorites,
    isFavorite,
    toggleFavorite,
    getVehicleSvg
  };
})(window);
