from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = "public/home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["categories"] = [
            {"name": "Гар утас", "emoji": "📱"},
            {"name": "Нөүтбүүк", "emoji": "💻"},
            {"name": "Таблет", "emoji": "📲"},
            {"name": "Камер", "emoji": "📷"},
            {"name": "Утасны плат", "emoji": "🔧"},
            {"name": "Бусад", "emoji": "📦"},
        ]
        return ctx
