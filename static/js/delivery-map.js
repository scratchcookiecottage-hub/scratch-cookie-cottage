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
          attributionControl: true,
        });
        el._leaflet_map = map;
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 18,
          attribution: "&copy; OpenStreetMap",
        }).addTo(map);

        const layer = L.geoJSON(geo, {
          style: function (feature) {
            const zip = (feature.properties && feature.properties.ZIPCODE) || "";
            const home = zip === "78746";
            return {
              color: home ? "#3d3229" : "#8a6a4f",
              weight: home ? 2.4 : 1.4,
              fillColor: home ? "#c4a574" : "#e6d3bc",
              fillOpacity: home ? 0.72 : 0.55,
            };
          },
          onEachFeature: function (feature, lyr) {
            const zip = (feature.properties && feature.properties.ZIPCODE) || "";
            lyr.bindPopup("<strong>" + zip + "</strong>");
          },
        }).addTo(map);

        const bounds = layer.getBounds();
        if (bounds.isValid()) {
          map.fitBounds(bounds, { padding: [18, 18] });
        } else {
          map.setView([30.28, -97.78], 11);
        }
      });
    })
    .catch(function () {
      maps.forEach(function (el) {
        el.innerHTML =
          "<p class=\"section-note\">Delivery area map could not load. See the ZIP list below.</p>";
      });
    });
})();
