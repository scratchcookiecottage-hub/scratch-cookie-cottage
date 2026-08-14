(function () {
  const maps = document.querySelectorAll(".delivery-map");
  if (!maps.length || typeof L === "undefined") return;

  const geoUrl = document.querySelector("[data-delivery-geo]")
    ? document.querySelector("[data-delivery-geo]").dataset.deliveryGeo
    : "/static/data/delivery-zips.geojson";

  fetch(geoUrl)
    .then(function (res) {
      if (!res.ok) throw new Error("Could not load delivery map");
      return res.json();
    })
    .then(function (geo) {
      maps.forEach(function (el) {
        const map = L.map(el, {
          scrollWheelZoom: false,
          attributionControl: false,
          zoomControl: true,
        });
        el._leaflet_map = map;
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 18,
        }).addTo(map);

        const layer = L.geoJSON(geo, {
          style: function (feature) {
            const zip = (feature.properties && feature.properties.ZIPCODE) || "";
            const home = zip === "78746";
            return {
              color: home ? "#1f6b3a" : "#2d8a4e",
              weight: home ? 2.4 : 1.4,
              fillColor: home ? "#3cb371" : "#7dce8f",
              fillOpacity: home ? 0.55 : 0.42,
            };
          },
          onEachFeature: function (feature, lyr) {
            const zip = (feature.properties && feature.properties.ZIPCODE) || "";
            lyr.bindPopup("<strong>" + zip + "</strong>");
          },
        }).addTo(map);

        const bounds = layer.getBounds();
        if (bounds.isValid()) {
          map.fitBounds(bounds, { padding: [48, 48], maxZoom: 10 });
          map.setZoom(map.getZoom() - 1);
        } else {
          map.setView([30.28, -97.78], 10);
        }
      });
    })
    .catch(function () {
      maps.forEach(function (el) {
        el.innerHTML =
          "<p class=\"section-note\">Delivery area map could not load.</p>";
      });
    });
})();
