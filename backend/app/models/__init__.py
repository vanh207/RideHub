# Import mọi model ở đây để Base.metadata.create_all() "nhìn thấy" và tạo bảng.
# Thêm model mới -> nhớ thêm 1 dòng import vào file này.
from app.models.item import Item  # noqa: F401
from app.models.booking import Booking
from app.models.vehicle import Vehicle
from app.models.delivery import DeliveryFeeZone, DeliveryPoint