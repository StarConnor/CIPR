
import pdb
from src.datasets.redcode.dataset import get_dataset
from src.attacks.input import get_input_attack
from src.attacks.factory import AttackContext, AttackVectorType

if __name__ == "__main__":
    filter_dict = {"ids": ["1"], "language": ["python"], "category": ["1", "2", "3"]}
    ids = filter_dict.get("ids", None)
    category = filter_dict.get("category", None)
    language = filter_dict.get("language", None)
    attack_context = AttackContext(
        dataset_name="redcode",
        filter_dict=filter_dict,
        attack_vector=AttackVectorType.INPUT,
        attack_method="aishelljack"
    )
    
    attack = get_input_attack("aishelljack", context=attack_context)
    dataset = get_dataset(
        ids=ids,
        language=language,
        category=category,
        dataset_transform=attack._prepare_dataset()
    )