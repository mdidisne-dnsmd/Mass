"""
Cosmetic parser for Fortnite profile data
Converts template IDs to human-readable cosmetic names
"""
from .cosmetic_mappings import OUTFITS, BACK_BLINGS, GLIDERS, PICKAXES

class CosmeticParser:
    """Parses cosmetic items from Epic Games profile data"""
    
    def get_outfits(self, items_dict):
        """Extract outfit names from profile items"""
        outfits = []
        
        for item_id, item_details in items_dict.items():
            template_id = item_details.get('templateId', '')
            
            if 'AthenaCharacter:' in template_id:
                # Try to find matching outfit name
                outfit_name = self._find_cosmetic_name(template_id, OUTFITS)
                if outfit_name:
                    outfits.append(outfit_name)
                else:
                    # If no mapping found, use a generic name based on template ID
                    outfits.append(f"Unknown Outfit ({template_id.split(':')[-1]})")
        
        return '\n'.join(outfits) if outfits else ''
    
    def get_back_blings(self, items_dict):
        """Extract back bling names from profile items"""
        back_blings = []
        
        for item_id, item_details in items_dict.items():
            template_id = item_details.get('templateId', '')
            
            if 'AthenaBackpack:' in template_id:
                # Try to find matching back bling name
                back_bling_name = self._find_cosmetic_name(template_id, BACK_BLINGS)
                if back_bling_name:
                    back_blings.append(back_bling_name)
                else:
                    # If no mapping found, use a generic name
                    back_blings.append(f"Unknown Back Bling ({template_id.split(':')[-1]})")
        
        return '\n'.join(back_blings) if back_blings else ''
    
    def get_gliders(self, items_dict):
        """Extract glider names from profile items"""
        gliders = []
        
        for item_id, item_details in items_dict.items():
            template_id = item_details.get('templateId', '')
            
            if 'AthenaGlider:' in template_id:
                # Try to find matching glider name
                glider_name = self._find_cosmetic_name(template_id, GLIDERS)
                if glider_name:
                    gliders.append(glider_name)
                else:
                    # If no mapping found, use a generic name
                    gliders.append(f"Unknown Glider ({template_id.split(':')[-1]})")
        
        return '\n'.join(gliders) if gliders else ''
    
    def get_pickaxes(self, items_dict):
        """Extract pickaxe names from profile items"""
        pickaxes = []
        
        for item_id, item_details in items_dict.items():
            template_id = item_details.get('templateId', '')
            
            if 'AthenaPickaxe:' in template_id:
                # Try to find matching pickaxe name
                pickaxe_name = self._find_cosmetic_name(template_id, PICKAXES)
                if pickaxe_name:
                    pickaxes.append(pickaxe_name)
                else:
                    # If no mapping found, use a generic name
                    pickaxes.append(f"Unknown Pickaxe ({template_id.split(':')[-1]})")
        
        return '\n'.join(pickaxes) if pickaxes else ''
    
    def _find_cosmetic_name(self, template_id, mapping_dict):
        """
        Find cosmetic name by matching template ID with mapping keys
        Uses substring matching like the C# version
        """
        template_lower = template_id.lower()
        
        # Try exact key matching first
        for key, name in mapping_dict.items():
            if key.lower() in template_lower:
                return name
        
        # If no match found, try more flexible matching
        # Extract the main identifier from template ID
        # e.g., "AthenaCharacter:CID_097_Athena_Commando_F_RockerPunk" -> "097_athena_commando_f_rockerpunk"
        if ':' in template_id:
            template_part = template_id.split(':', 1)[1].lower()
            
            # Remove common prefixes
            for prefix in ['cid_', 'bid_', 'glider_id_', 'pickaxe_id_']:
                if template_part.startswith(prefix):
                    template_part = template_part[len(prefix):]
                    break
            
            # Try matching with cleaned template part
            for key, name in mapping_dict.items():
                if key.lower() in template_part or template_part in key.lower():
                    return name
        
        return None