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
package agent;

import com.consts.Constants.EnumOptSchemeNeb;
import com.consts.Constants.EnumStringMethod;

public class InputAgentNeb extends InputAgent{
	/**
	 * 
	 */
	private static final long serialVersionUID = 5327711272416053942L;

	public int startGeo;
	public int endGeo;
	public WrapperBoolean boolMinImage;
	
	public WrapperEnum enumMethod;
	public WrapperBoolean boolRestart;
	public WrapperInteger numOfImages;
	public WrapperInteger nstepPath;
	public WrapperDouble pathThr;
	public WrapperDouble ds;
	public WrapperEnum enumOptScheme;
	public WrapperBoolean boolCI;
	public WrapperBoolean firstLastOpt;
	
	public InputAgentNeb() {
		startGeo=0;
		endGeo=0;
		boolMinImage=new WrapperBoolean(false);
		
		enumMethod=new WrapperEnum(EnumStringMethod.neb);
		boolRestart=new WrapperBoolean(false);
		numOfImages=new WrapperInteger(8,true);//not QE default
		nstepPath=new WrapperInteger(50,true);
		pathThr=new WrapperDouble(0.05);
		ds=new WrapperDouble(1.0);
		enumOptScheme=new WrapperEnum(EnumOptSchemeNeb.qm);
		boolCI=new WrapperBoolean(false);
		firstLastOpt=new WrapperBoolean(false);
	}
	@Override
	public boolean convertInfoFromInput(String inputStr) {
		// TODO Auto-generated method stub
		return false;
	}
}
