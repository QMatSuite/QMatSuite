/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package input;


import com.consts.Constants.EnumNameList;
import com.programconst.DefaultFileNamesQE;

import core.agent.WrapperInteger;
import core.agent.WrapperString;
import core.com.error.InvalidKeyException;
import core.com.error.InvalidTypeException;
import core.input.InputValueInt;
import core.input.InputValueString;


public class BandsInput extends QeInput{
	
	public BandsInput() {
		super("bands");
		sectionDict.put("BANDS", new NameList(EnumNameList.BANDS));
		sectionDict.get("BANDS").setBoolRequired(true);
		sectionDict.get("BANDS").addParameter("outdir", new InputValueString("outdir",DefaultFileNamesQE.outDir,true));//always write
		sectionDict.get("BANDS").addParameter("filband", new InputValueString("filband","bands.out",true));//always write
		
		sectionDict.get("BANDS").addParameter("spin_component", new InputValueInt("spin_component",false));
	}
	public void setNoSpin() {
		try {
			setRequiredAndWrite("BANDS","spin_component",false,false);
			setValue("BANDS","filband",new WrapperString(DefaultFileNamesQE.bandsDatGnu,true));
			
		} catch (InvalidKeyException | InvalidTypeException e) {
			e.printStackTrace();
		}
	}
	public void setSpinUp() {
		try {
			setValue("BANDS","spin_component",new WrapperInteger(1,true));setRequiredAndWrite("BANDS","spin_component",true,true);
			setValue("BANDS","filband",new WrapperString(DefaultFileNamesQE.bandsDatGnu+".spinup",true));
		} catch (InvalidKeyException | InvalidTypeException e) {
			e.printStackTrace();
		}
	}
	public void setSpinDown() {
		try {
			setValue("BANDS","spin_component",new WrapperInteger(2,true));setRequiredAndWrite("BANDS","spin_component",true,true);
			setValue("BANDS","filband",new WrapperString(DefaultFileNamesQE.bandsDatGnu+".spindown",true));
		} catch (InvalidKeyException | InvalidTypeException e) {
			e.printStackTrace();
		}
	}
	
}
