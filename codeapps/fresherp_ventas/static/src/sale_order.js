import { FormController } from "@web/views/form/form_controller";
import { registry } from "@web/core/registry";

export class CustomSaleOrder extends FormController {
    setup() {
        super.setup();
        console.log("My custom form view is loaded!");
        // Add your custom logic here
    }

}
registry.category("views").add("fresherp_sale_order", CustomSaleOrder);
